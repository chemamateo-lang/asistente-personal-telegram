"""
Asistente Personal de Telegram — punto de entrada único.

Funcionalidades:
  - Chat IA con memoria por usuario (Groq/llama-3.3-70b + fallback OpenAI/gpt-4o-mini)
  - Transcripción de notas de voz (Whisper) y análisis de imágenes (GPT-4o Vision)
  - Modos de respuesta: normal / concise / creative
  - Lista de la compra persistente (SQLite)
  - Tareas pendientes con estado toggle
  - Agenda: citas con notas y alarmas proactivas (JobQueue interno)
  - Respuestas en voz via OpenAI TTS con acento y velocidad configurables
  - Rate limiting diario por usuario con notificación al administrador
"""

import asyncio
import datetime
import os
import logging
import tempfile
from collections import defaultdict, deque

import groq
import openai
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
from telegram import BotCommand, Update, constants
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

import documentos
import keyboards
import utils

import database
from config import (
    GROQ_API_KEY, OPENAI_API_KEY, TELEGRAM_TOKEN, SYSTEM_PROMPT,
    ADMIN_USER_ID, LIMITE_IA_DIARIO,
)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Clientes de IA
# ---------------------------------------------------------------------------
groq_client = groq.Groq(api_key=GROQ_API_KEY)
openai_client = openai.OpenAI(api_key=OPENAI_API_KEY)

# ---------------------------------------------------------------------------
# Rate limiting — helpers async (DB es síncrona, se ejecuta en thread pool)
# ---------------------------------------------------------------------------

async def _check_rate_limit(update: Update) -> bool:
    """Devuelve False y responde al usuario si superó el límite diario."""
    if LIMITE_IA_DIARIO == 0:
        return True
    user_id = update.effective_user.id
    uso = await asyncio.to_thread(database.get_uso_ia_hoy, user_id)
    if uso >= LIMITE_IA_DIARIO:
        await update.message.reply_text(
            f"Has alcanzado tu límite diario de {LIMITE_IA_DIARIO} consultas. "
            "Vuelve mañana o contacta con el administrador."
        )
        return False
    return True


async def _increment_and_notify(ctx: ContextTypes.DEFAULT_TYPE, user_id: int) -> None:
    """Incrementa el contador y avisa al admin cada 5 usos."""
    nuevo_total = await asyncio.to_thread(database.incrementar_uso_ia, user_id)
    if ADMIN_USER_ID and nuevo_total % 5 == 0:
        await ctx.bot.send_message(
            ADMIN_USER_ID,
            f"📊 Usuario {user_id} lleva {nuevo_total} consultas de IA hoy.",
        )


# ---------------------------------------------------------------------------
# Memoria por usuario: deque circular de max 15 mensajes
# ---------------------------------------------------------------------------
MEMORY_SIZE = 15
user_memory: dict[int, deque] = defaultdict(lambda: deque(maxlen=MEMORY_SIZE))
# Modo actual de cada usuario: "normal" | "concise" | "creative"
user_mode: dict[int, str] = defaultdict(lambda: "normal")

MODE_INSTRUCTIONS = {
    "normal":   "Responde de forma completa y equilibrada.",
    "concise":  "Responde en máximo 3 frases. Sé ultra-conciso.",
    "creative": "Responde con creatividad, metáforas y ejemplos originales.",
}

# ---------------------------------------------------------------------------
# Helpers de construcción de mensajes
# ---------------------------------------------------------------------------

def build_messages(user_id: int, new_user_message: str) -> list[dict]:
    """Construye el array de mensajes para la API incluyendo historial."""
    mode = user_mode[user_id]
    system = f"{SYSTEM_PROMPT}\n\n{MODE_INSTRUCTIONS[mode]}"
    messages = [{"role": "system", "content": system}]
    messages.extend(user_memory[user_id])
    messages.append({"role": "user", "content": new_user_message})
    return messages


def save_exchange(user_id: int, user_text: str, assistant_text: str) -> None:
    """Guarda el turno de conversación en la memoria circular del usuario."""
    user_memory[user_id].append({"role": "user", "content": user_text})
    user_memory[user_id].append({"role": "assistant", "content": assistant_text})


# ---------------------------------------------------------------------------
# Llamadas a LLM con reintentos y fallback
# ---------------------------------------------------------------------------

@retry(
    retry=retry_if_exception_type((groq.APIConnectionError, groq.RateLimitError)),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    stop=stop_after_attempt(3),
)
def _call_groq(messages: list[dict]) -> str:
    response = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=messages,
        max_tokens=800,
        temperature=0.7,
    )
    return response.choices[0].message.content.strip()


@retry(
    retry=retry_if_exception_type((openai.APIConnectionError, openai.RateLimitError)),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    stop=stop_after_attempt(3),
)
def _call_openai(messages: list[dict]) -> str:
    response = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        max_tokens=800,
        temperature=0.7,
    )
    return response.choices[0].message.content.strip()


def call_llm(messages: list[dict]) -> str:
    """Intenta Groq primero; si falla hace fallback a OpenAI."""
    try:
        logger.info("Llamando a Groq...")
        return _call_groq(messages)
    except Exception as groq_err:
        logger.warning(f"Groq falló ({groq_err}). Usando fallback OpenAI...")
        try:
            return _call_openai(messages)
        except Exception as oai_err:
            logger.error(f"OpenAI también falló: {oai_err}")
            raise RuntimeError("Ambos proveedores de IA no responden.") from oai_err


# ---------------------------------------------------------------------------
# Transcripción de voz
# ---------------------------------------------------------------------------

async def transcribe_voice(file_bytes: bytes, mime: str = "audio/ogg") -> str:
    """Transcribe un audio usando Whisper de OpenAI."""
    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
        tmp.write(file_bytes)
        tmp_path = tmp.name

    try:
        with open(tmp_path, "rb") as audio_file:
            transcript = openai_client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                language="es",
            )
        return transcript.text.strip()
    finally:
        os.unlink(tmp_path)


# ---------------------------------------------------------------------------
# Análisis de imágenes (gpt-4o Vision)
# ---------------------------------------------------------------------------

async def analyze_image(image_bytes: bytes, caption: str = "") -> str:
    """Analiza una imagen usando GPT-4o Vision."""
    import base64
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    user_prompt = caption if caption else "Describe detalladamente esta imagen."

    response = openai_client.chat.completions.create(
        model="gpt-4o",
        max_tokens=800,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user_prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
                    },
                ],
            }
        ],
    )
    return response.choices[0].message.content.strip()


# ---------------------------------------------------------------------------
# Lista de la compra
# ---------------------------------------------------------------------------

async def cmd_lista(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    articulo = " ".join(ctx.args) if ctx.args else ""
    if not articulo:
        await update.message.reply_text(
            "Indica qué quieres añadir. Ejemplo: `/lista leche`",
            parse_mode=constants.ParseMode.MARKDOWN,
        )
        return
    await asyncio.to_thread(database.add_compra, user_id, articulo)
    await update.message.reply_text(
        f"✅ Añadido a la compra: *{articulo}*",
        parse_mode=constants.ParseMode.MARKDOWN,
    )


async def cmd_comprar(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    items = await asyncio.to_thread(database.get_compras, user_id)
    if not items:
        await update.message.reply_text(
            "Tu lista de la compra está vacía. Añade artículos con `/lista <artículo>`.",
            parse_mode=constants.ParseMode.MARKDOWN,
        )
        return
    markup = keyboards.get_compras_keyboard(items)
    await update.message.reply_text(
        "🛒 *Tu Lista de la Compra:*",
        reply_markup=markup,
        parse_mode=constants.ParseMode.MARKDOWN,
    )


async def callback_compra(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    accion, item_id_str = query.data.split("_", 1)
    item_id = int(item_id_str)

    if accion == "toggle":
        await asyncio.to_thread(database.toggle_compra, item_id)
    else:
        await asyncio.to_thread(database.delete_compra, item_id)

    user_id = query.from_user.id
    items = await asyncio.to_thread(database.get_compras, user_id)

    if not items:
        await query.edit_message_text("🛒 Lista de la compra vacía.")
        return

    try:
        await query.edit_message_reply_markup(
            reply_markup=keyboards.get_compras_keyboard(items)
        )
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Tareas pendientes
# ---------------------------------------------------------------------------

async def cmd_tarea(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    texto = " ".join(ctx.args) if ctx.args else ""
    if not texto:
        await update.message.reply_text(
            "Indica la tarea que quieres añadir. Ejemplo: `/tarea regar las plantas`",
            parse_mode=constants.ParseMode.MARKDOWN,
        )
        return
    await asyncio.to_thread(database.add_tarea, user_id, texto)
    await update.message.reply_text(
        f"✅ Tarea añadida: *{texto}*",
        parse_mode=constants.ParseMode.MARKDOWN,
    )


async def cmd_pendientes(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    tareas = await asyncio.to_thread(database.get_tareas_usuario, user_id)
    if not tareas:
        await update.message.reply_text(
            "🎉 No tienes tareas pendientes. Añade una con `/tarea <texto>`.",
            parse_mode=constants.ParseMode.MARKDOWN,
        )
        return
    markup = keyboards.get_tareas_keyboard(tareas)
    await update.message.reply_text(
        "📝 *Tus Tareas Pendientes:*",
        reply_markup=markup,
        parse_mode=constants.ParseMode.MARKDOWN,
    )


async def callback_tarea(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    accion, item_id_str = query.data.split("_", 1)
    item_id = int(item_id_str)

    if accion == "toggletarea":
        await asyncio.to_thread(database.toggle_tarea, item_id)
    else:
        await asyncio.to_thread(database.delete_tarea, item_id)

    user_id = query.from_user.id
    tareas = await asyncio.to_thread(database.get_tareas_usuario, user_id)

    if not tareas:
        await query.edit_message_text("📝 No tienes tareas pendientes.")
        return

    try:
        await query.edit_message_reply_markup(
            reply_markup=keyboards.get_tareas_keyboard(tareas)
        )
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Agenda y citas
# ---------------------------------------------------------------------------

# Estados internos del ConversationHandler
_TITULO, _FECHA, _NOTA, _ALARMA = range(4)


async def cmd_nueva_cita(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "📝 Vamos a crear una nueva cita.\n\n¿Cuál es el *título* o asunto?",
        parse_mode=constants.ParseMode.MARKDOWN,
    )
    return _TITULO


async def _process_titulo(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    ctx.user_data["cita_titulo"] = update.message.text
    await update.message.reply_text(
        "📅 Ahora dime la *fecha* (ej: 30-06-2026, Mañana, etc.):",
        parse_mode=constants.ParseMode.MARKDOWN,
    )
    return _FECHA


async def _process_fecha(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    titulo = ctx.user_data.pop("cita_titulo", "Sin título")
    fecha = update.message.text
    cita_id = await asyncio.to_thread(database.add_cita, user_id, titulo, fecha)
    markup = keyboards.get_cita_opciones_keyboard(cita_id)
    await update.message.reply_text(
        f"✅ *Cita guardada*\n\n📌 *Asunto:* {titulo}\n📅 *Fecha:* {fecha}\n\n¿Qué más quieres hacer?",
        reply_markup=markup,
        parse_mode=constants.ParseMode.MARKDOWN,
    )
    return ConversationHandler.END


async def _cb_inicio_nota(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    cita_id = int(query.data.split("_")[2])
    ctx.user_data["cita_id_nota"] = cita_id
    notas = await asyncio.to_thread(database.get_notas_by_cita, cita_id)
    if notas:
        texto = "📝 *Notas actuales:*\n\n" + "\n".join(f"• {n[1]}" for n in notas)
        texto += "\n\nEscribe una nueva nota o *cancelar*:"
    else:
        texto = "No hay notas para esta cita.\n\nEscribe la nota que quieres añadir o *cancelar*:"
    await query.message.reply_text(texto, parse_mode=constants.ParseMode.MARKDOWN)
    return _NOTA


async def _process_nota(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.text.lower().strip() == "cancelar":
        await update.message.reply_text("Acción cancelada.")
        return ConversationHandler.END
    cita_id = ctx.user_data.pop("cita_id_nota")
    await asyncio.to_thread(database.add_nota, cita_id, update.message.text)
    markup = keyboards.get_cita_opciones_keyboard(cita_id)
    await update.message.reply_text("✅ Nota guardada. ¿Qué más quieres hacer?", reply_markup=markup)
    return ConversationHandler.END


async def _cb_inicio_alarma(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    cita_id = int(query.data.split("_")[2])
    ctx.user_data["cita_id_alarma"] = cita_id
    alarmas = await asyncio.to_thread(database.get_alarmas_by_cita, cita_id)
    if alarmas:
        texto = "⏰ *Alarmas actuales:*\n\n" + "\n".join(f"• 🔔 {a[1]}" for a in alarmas)
        texto += "\n\nEscribe cuándo quieres añadir otra alarma o *cancelar*:"
    else:
        texto = "⏰ No hay alarmas.\n\nEscribe cuándo quieres el aviso\n(ej: '30 minutos antes', '26-06-2026 10:00') o *cancelar*:"
    await query.message.reply_text(texto, parse_mode=constants.ParseMode.MARKDOWN)
    return _ALARMA


async def _process_alarma(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.text.lower().strip() == "cancelar":
        await update.message.reply_text("Acción cancelada.")
        return ConversationHandler.END
    cita_id = ctx.user_data.pop("cita_id_alarma")
    await asyncio.to_thread(database.add_alarma, cita_id, update.message.text)
    markup = keyboards.get_cita_opciones_keyboard(cita_id)
    await update.message.reply_text("✅ Alarma guardada. ¿Qué más quieres hacer?", reply_markup=markup)
    return ConversationHandler.END


async def _cancelar_conversacion(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    ctx.user_data.clear()
    await update.message.reply_text("Operación cancelada.")
    return ConversationHandler.END


def _build_citas_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CommandHandler("cita", cmd_nueva_cita),
            CallbackQueryHandler(_cb_inicio_nota, pattern=r"^cita_notas_\d+$"),
            CallbackQueryHandler(_cb_inicio_alarma, pattern=r"^cita_alarmas_\d+$"),
        ],
        states={
            _TITULO: [MessageHandler(filters.TEXT & ~filters.COMMAND, _process_titulo)],
            _FECHA:  [MessageHandler(filters.TEXT & ~filters.COMMAND, _process_fecha)],
            _NOTA:   [MessageHandler(filters.TEXT & ~filters.COMMAND, _process_nota)],
            _ALARMA: [MessageHandler(filters.TEXT & ~filters.COMMAND, _process_alarma)],
        },
        fallbacks=[CommandHandler("cancelar", _cancelar_conversacion)],
        per_message=False,
    )


async def cmd_agenda(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    citas = await asyncio.to_thread(database.get_citas_usuario, user_id)
    if not citas:
        await update.message.reply_text(
            "📅 No tienes ninguna cita programada. Crea una con `/cita`.",
            parse_mode=constants.ParseMode.MARKDOWN,
        )
        return
    markup = keyboards.get_lista_citas_keyboard(citas)
    await update.message.reply_text(
        "📌 *Tus Citas Guardadas:*\nSelecciona una para ver sus opciones:",
        reply_markup=markup,
        parse_mode=constants.ParseMode.MARKDOWN,
    )


async def callback_ver_cita(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    cita_id = int(query.data.split("_")[2])
    markup = keyboards.get_cita_opciones_keyboard(cita_id)
    await query.message.reply_text("⚙️ ¿Qué deseas gestionar de esta cita?", reply_markup=markup)


async def callback_cita_borrar(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    cita_id = int(query.data.split("_")[2])
    await asyncio.to_thread(database.delete_cita, cita_id)
    await query.edit_message_text(
        "🗑️ *Cita eliminada* junto con sus notas y alarmas.",
        parse_mode=constants.ParseMode.MARKDOWN,
    )


# ---------------------------------------------------------------------------
# Preferencias de voz y TTS
# ---------------------------------------------------------------------------

async def _send_tts_reply(update: Update, text: str, user_id: int) -> None:
    """Genera y envía respuesta en audio si el usuario tiene la voz activada."""
    if not await asyncio.to_thread(database.get_voz_activa, user_id):
        return
    acento, velocidad = await asyncio.to_thread(database.get_preferencias_voz, user_id)
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
        tmp_path = tmp.name
    try:
        result = await asyncio.to_thread(
            utils.generar_audio_tts, text, acento, velocidad, tmp_path
        )
        if result:
            with open(tmp_path, "rb") as audio:
                await update.message.reply_audio(audio)
    except Exception as e:
        logger.error(f"Error generando TTS: {e}")
    finally:
        await asyncio.to_thread(utils.limpiar_archivos_temporales, tmp_path)


async def cmd_voz(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    acento, velocidad = await asyncio.to_thread(database.get_preferencias_voz, user_id)
    voz_activa = await asyncio.to_thread(database.get_voz_activa, user_id)
    markup = keyboards.get_preferencias_voz_keyboard(acento, velocidad, voz_activa)
    await update.message.reply_text(
        "🎙️ *Configuración de voz*\nSelecciona acento, velocidad y activa/desactiva las respuestas habladas:",
        reply_markup=markup,
        parse_mode=constants.ParseMode.MARKDOWN,
    )


async def callback_voz_preferencias(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    partes = query.data.split("_", 1)
    tipo, valor = partes[0], partes[1]

    if tipo == "acento":
        await asyncio.to_thread(database.update_acento, user_id, valor)
        await query.answer(f"Acento: {valor.upper()}", show_alert=False)
    elif tipo == "vel":
        await asyncio.to_thread(database.update_velocidad, user_id, valor)
        await query.answer(f"Velocidad: {valor}x", show_alert=False)

    acento, velocidad = await asyncio.to_thread(database.get_preferencias_voz, user_id)
    voz_activa = await asyncio.to_thread(database.get_voz_activa, user_id)
    try:
        await query.edit_message_reply_markup(
            reply_markup=keyboards.get_preferencias_voz_keyboard(acento, velocidad, voz_activa)
        )
    except Exception:
        pass


async def callback_toggle_voz(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user_id = query.from_user.id
    nuevo_estado = await asyncio.to_thread(database.toggle_voz_activa, user_id)
    await query.answer("Voz activada ✅" if nuevo_estado else "Voz desactivada 🔇")
    acento, velocidad = await asyncio.to_thread(database.get_preferencias_voz, user_id)
    try:
        await query.edit_message_reply_markup(
            reply_markup=keyboards.get_preferencias_voz_keyboard(acento, velocidad, nuevo_estado)
        )
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Alarmas proactivas (JobQueue)
# ---------------------------------------------------------------------------

_ALARM_FORMATS = ("%d-%m-%Y %H:%M", "%Y-%m-%d %H:%M", "%d/%m/%Y %H:%M")


def _parse_alarm_datetime(tiempo_aviso: str) -> datetime.datetime | None:
    """Parsea tiempo_aviso como datetime absoluto; devuelve None si no lo reconoce."""
    for fmt in _ALARM_FORMATS:
        try:
            return datetime.datetime.strptime(tiempo_aviso.strip(), fmt)
        except ValueError:
            continue
    return None


async def job_check_alarmas(ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Job periódico: envía las alarmas pendientes cuya hora ya ha llegado."""
    alarmas = await asyncio.to_thread(database.get_alarmas_pendientes)
    if not alarmas:
        return

    ahora = datetime.datetime.now()
    for alarma_id, cita_id, tiempo_aviso, titulo, user_id in alarmas:
        alarm_dt = _parse_alarm_datetime(tiempo_aviso)
        if alarm_dt is not None and ahora < alarm_dt:
            continue  # Aún no es la hora

        try:
            await ctx.bot.send_message(
                user_id,
                f"⏰ *Aviso de cita*\n\n📌 *{titulo}*\n🕐 Configurado: _{tiempo_aviso}_",
                parse_mode=constants.ParseMode.MARKDOWN,
            )
            await asyncio.to_thread(database.marcar_alarma_enviada, alarma_id)
            logger.info(f"Alarma {alarma_id} enviada a user_id={user_id}")
        except Exception as e:
            logger.error(f"Error enviando alarma {alarma_id}: {e}")


# ---------------------------------------------------------------------------
# Handlers de Telegram
# ---------------------------------------------------------------------------

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    await update.message.reply_text(
        f"Hola, {user.first_name}. Soy tu asistente personal.\n\n"
        "Puedes hablarme por texto, enviarme notas de voz o fotos.\n\n"
        "Comandos disponibles:\n"
        "/ayuda — ver todos los comandos\n"
        "/reset — borrar memoria de conversación\n"
        "/mode — cambiar estilo de respuesta\n"
        "/resume — últimos 5 mensajes de contexto"
    )


async def cmd_ayuda(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "*Comandos disponibles*\n\n"
        "🤖 *Chat IA*\n"
        "Escribe cualquier mensaje para conversar con la IA.\n"
        "• `/reset` — borrar historial de conversación\n"
        "• `/mode normal|concise|creative` — cambiar estilo de respuesta\n"
        "• `/resume` — ver los últimos mensajes en memoria\n\n"
        "🛒 *Lista de la compra*\n"
        "• `/lista <artículo>` — añadir artículo\n"
        "• `/comprar` — ver y gestionar la lista\n\n"
        "📝 *Tareas*\n"
        "• `/tarea <texto>` — añadir tarea\n"
        "• `/pendientes` — ver y gestionar tareas\n\n"
        "📅 *Agenda*\n"
        "• `/cita` — crear nueva cita paso a paso\n"
        "• `/agenda` — ver y gestionar citas\n"
        "• `/cancelar` — cancelar operación en curso\n\n"
        "🎙️ *Voz*\n"
        "• `/voz` — configurar acento, velocidad y activar/desactivar respuestas habladas\n"
        "También puedes enviar notas de voz o fotos.\n\n"
        "🗂️ *Documentos*\n"
        "Envía un PDF o archivo y te pregunto la carpeta.\n"
        "Foto con el texto `doc` → se guarda como documento.\n"
        "• `/docs` — ver carpetas y recibir documentos\n"
        "• `/buscar <texto>` — buscar por nombre\n\n"
        "⚙️ *Sistema*\n"
        "• `/start` — mensaje de bienvenida\n"
        "• `/ayuda` — este mensaje",
        parse_mode=constants.ParseMode.MARKDOWN,
    )


async def cmd_reset(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    user_memory[user_id].clear()
    await update.message.reply_text("Memoria borrada. Empezamos de cero.")
    logger.info(f"Reset de memoria: user_id={user_id}")


async def cmd_mode(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    args = ctx.args
    valid_modes = list(MODE_INSTRUCTIONS.keys())

    if not args or args[0] not in valid_modes:
        current = user_mode[user_id]
        await update.message.reply_text(
            f"Modo actual: {current}\n\n"
            f"Usa /mode <modo>. Opciones: {', '.join(valid_modes)}"
        )
        return

    user_mode[user_id] = args[0]
    await update.message.reply_text(f"Modo cambiado a: {args[0]}")


async def cmd_resume(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    history = list(user_memory[user_id])[-10:]  # últimos 5 turnos (10 mensajes)

    if not history:
        await update.message.reply_text("No hay historial en memoria.")
        return

    lines = []
    for msg in history:
        rol = "Tú" if msg["role"] == "user" else "Bot"
        contenido = msg["content"][:120]
        if len(msg["content"]) > 120:
            contenido += "…"
        lines.append(f"*{rol}:* {contenido}")

    await update.message.reply_text(
        "\n\n".join(lines),
        parse_mode=constants.ParseMode.MARKDOWN,
    )


async def handle_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    text = update.message.text
    logger.info(f"Texto de user_id={user_id}: {text[:80]}")

    if not await _check_rate_limit(update):
        return

    await ctx.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action=constants.ChatAction.TYPING,
    )

    try:
        messages = build_messages(user_id, text)
        reply = call_llm(messages)
        save_exchange(user_id, text, reply)
        await update.message.reply_text(reply)
        await _send_tts_reply(update, reply, user_id)
        await _increment_and_notify(ctx, user_id)
    except Exception as e:
        logger.error(f"Error en handle_text: {e}")
        await update.message.reply_text(
            "Lo siento, en este momento no puedo responder. Inténtalo en unos segundos."
        )


async def handle_voice(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    logger.info(f"Nota de voz de user_id={user_id}")

    if not await _check_rate_limit(update):
        return

    await ctx.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action=constants.ChatAction.TYPING,
    )

    try:
        voice_file = await ctx.bot.get_file(update.message.voice.file_id)
        audio_bytes = await voice_file.download_as_bytearray()

        transcription = await transcribe_voice(bytes(audio_bytes))
        logger.info(f"Transcripción: {transcription[:80]}")

        if not transcription:
            await update.message.reply_text("No pude entender el audio. ¿Puedes repetirlo?")
            return

        messages = build_messages(user_id, transcription)
        reply = call_llm(messages)
        save_exchange(user_id, transcription, reply)

        await update.message.reply_text(
            f"🎙️ *Transcripción:* _{transcription}_\n\n{reply}",
            parse_mode=constants.ParseMode.MARKDOWN,
        )
        await _increment_and_notify(ctx, user_id)
    except Exception as e:
        logger.error(f"Error en handle_voice: {e}")
        await update.message.reply_text("No pude procesar el audio. Inténtalo de nuevo.")


async def handle_photo(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    caption = update.message.caption or ""
    logger.info(f"Foto de user_id={user_id}, caption='{caption[:60]}'")

    if not await _check_rate_limit(update):
        return

    await ctx.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action=constants.ChatAction.TYPING,
    )

    try:
        photo = update.message.photo[-1]
        photo_file = await ctx.bot.get_file(photo.file_id)
        image_bytes = await photo_file.download_as_bytearray()

        analysis = await analyze_image(bytes(image_bytes), caption)
        save_exchange(user_id, f"[Imagen enviada] {caption}", analysis)
        await update.message.reply_text(analysis)
        await _increment_and_notify(ctx, user_id)
    except Exception as e:
        logger.error(f"Error en handle_photo: {e}")
        await update.message.reply_text("No pude analizar la imagen. Inténtalo de nuevo.")


# ---------------------------------------------------------------------------
# Punto de entrada
# ---------------------------------------------------------------------------

def main() -> None:
    if not TELEGRAM_TOKEN:
        logger.error("TELEGRAM_TOKEN no configurado en .env")
        raise SystemExit(1)

    database.init_db()
    logger.info("Base de datos inicializada.")

    async def post_init(app) -> None:
        await app.bot.set_my_commands([
            BotCommand("start",      "Mensaje de bienvenida"),
            BotCommand("ayuda",      "Ver todos los comandos"),
            BotCommand("reset",      "Borrar historial de conversación"),
            BotCommand("mode",       "Cambiar modo: normal | concise | creative"),
            BotCommand("resume",     "Ver últimos mensajes en memoria"),
            BotCommand("lista",      "Añadir artículo a la lista de la compra"),
            BotCommand("comprar",    "Ver y gestionar la lista de la compra"),
            BotCommand("tarea",      "Añadir tarea pendiente"),
            BotCommand("pendientes", "Ver y gestionar tareas pendientes"),
            BotCommand("cita",       "Crear nueva cita paso a paso"),
            BotCommand("agenda",     "Ver y gestionar agenda de citas"),
            BotCommand("cancelar",   "Cancelar operación en curso"),
            BotCommand("voz",        "Configurar voz y respuestas habladas"),
            BotCommand("docs",       "Ver el archivo de documentos"),
            BotCommand("buscar",     "Buscar un documento por nombre"),
        ])
        logger.info("Comandos registrados en Telegram.")

    app = (
        ApplicationBuilder()
        .token(TELEGRAM_TOKEN)
        .post_init(post_init)
        .build()
    )

    app.job_queue.run_repeating(job_check_alarmas, interval=60, first=10)
    logger.info("Job de alarmas registrado (cada 60 s, primer disparo en 10 s).")

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("ayuda", cmd_ayuda))
    app.add_handler(CommandHandler("reset", cmd_reset))
    app.add_handler(CommandHandler("mode", cmd_mode))
    app.add_handler(CommandHandler("resume", cmd_resume))

    # Lista de la compra
    app.add_handler(CommandHandler("lista", cmd_lista))
    app.add_handler(CommandHandler("comprar", cmd_comprar))
    app.add_handler(CallbackQueryHandler(callback_compra, pattern=r"^(toggle|delete)_\d+$"))

    # Tareas pendientes
    app.add_handler(CommandHandler("tarea", cmd_tarea))
    app.add_handler(CommandHandler("pendientes", cmd_pendientes))
    app.add_handler(CallbackQueryHandler(callback_tarea, pattern=r"^(toggletarea|deletetarea)_\d+$"))

    # Preferencias de voz
    app.add_handler(CommandHandler("voz", cmd_voz))
    app.add_handler(CallbackQueryHandler(callback_voz_preferencias, pattern=r"^(acento|vel)_"))
    app.add_handler(CallbackQueryHandler(callback_toggle_voz, pattern=r"^toggle_voz$"))

    # Agenda y citas (ConversationHandler primero para capturar texto en flujos activos)
    app.add_handler(_build_citas_conversation())
    app.add_handler(CommandHandler("agenda", cmd_agenda))
    app.add_handler(CallbackQueryHandler(callback_ver_cita, pattern=r"^ver_cita_\d+$"))
    app.add_handler(CallbackQueryHandler(callback_cita_borrar, pattern=r"^cita_borrar_\d+$"))

    # Archivo de documentos (antes del handler genérico de fotos)
    documentos.registrar(app)

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    logger.info("Bot iniciado. Escuchando mensajes...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
