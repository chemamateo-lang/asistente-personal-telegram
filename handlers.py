# handlers.py
import os
import time
import logging
from telegram import Update
from telegram.ext import ContextTypes
from gtts import gTTS

from database import (
    increment_ia_usage,
    get_ia_usage,
    reset_ia_usage_db,
    is_admin,
    add_appointment_db
)
from keyboards import get_voice_settings_keyboard, get_main_menu_keyboard
from utils import get_ai_response

logger = logging.getLogger(__name__)

# --- Command Handlers ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Manda el mensaje de bienvenida con el menú principal."""
    user = update.effective_user
    await update.message.reply_text(
        f"¡Hola, {user.first_name}! Soy tu asistente personal modular. ¿En qué te puedo ayudar hoy?",
        reply_markup=get_main_menu_keyboard()
    )

async def set_voice_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Muestra el menú interactivo para configurar la voz (acento y velocidad)."""
    await update.message.reply_text(
        "Configura los parámetros de la voz para las respuestas de la IA:",
        reply_markup=get_voice_settings_keyboard()
    )

async def reset_ia(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Comando de administración para reiniciar el contador diario de IA."""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("Lo siento, no tienes permisos de administrador para ejecutar este comando.")
        return
        
    reset_ia_usagedb()
    await update.message.reply_text("✅ Contador diario de uso de IA reiniciado exitosamente para todos los usuarios.")

async def cita_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Inicia el asistente paso a paso para registrar un evento/cita."""
    await update.message.reply_text(
        "Iniciando asistente de citas...\n"
        "Por favor, dime los detalles de la cita respondiendo con el formato:\n"
        "<i>Título | Fecha y Hora (YYYY-MM-DD HH:MM) | Tiempo de aviso previo (minutos) | Nota opcional</i>\n\n"
        "Ejemplo: <code>Dentista | 2026-07-01 10:00 | 30 | Revisión anual</code>",
        parse_mode="HTML"
    )
    context.user_data["awaiting_appointment"] = True

# --- Test / Simulation Handlers ---

async def test_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Manejador de prueba para verificar que el bot responde correctamente."""
    user = update.effective_user
    logger.info(f"Ejecutando comando de prueba por el usuario {user.id}")
    
    await update.message.reply_text(
        f"¡Hola {user.first_name}! El sistema de handlers y comandos está funcionando correctamente. 🟢"
    )

async def test_echo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Manejador de eco para pruebas de texto plano."""
    text_received = update.message.text
    await update.message.reply_text(f"Eco de prueba recibido: {text_received}")

# --- Callback / Inline Keyboard Handlers ---

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Mestiona las selecciones de los teclados interactivos (configuración de voz)."""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    # Manejo de selección de acentos
    if data in ["es", "mx", "ar"]:
        context.user_data["voice_lang"] = data
        await query.edit_message_text(
            text=f"Acento configurado a: {data.upper()}. Ahora elige la velocidad:",
            reply_markup=get_voice_settings_keyboard(current_lang=data)
        )
    
    # Manejo de selección de velocidades
    elif data in ["0.8", "1.0", "1.2", "1.5", "2.0"]:
        context.user_data["voice_tempo"] = float(data)
        lang = context.user_data.get("voice_lang", "es")
        await query.edit_message_text(
            text=f"✅ Configuración guardada correctamente.\nIdioma: {lang.upper()} | Velocidad: {data}x"
        )

# --- Message Handler (Texto, IA, Notas de Voz y Asistente de Citas) ---

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Procesa los mensajes de texto, ya sea para el asistente de citas, llamadas a la IA o conversación general."""
    text = update.message.text
    user_id = update.effective_user.id
    
    # 1. Procesar asistente paso a paso de Citas
    if context.user_data.get("awaiting_appointment"):
        context.user_data["awaiting_appointment"] = False
        try:
            parts = [p.strip() for p in text.split("|")]
            if len(parts) < 3:
                raise ValueError("Formato incompleto.")
                
            title = parts[0]
            datetime_str = parts[1]
            alarm_offset = int(parts[2])
            note = parts[3] if len(parts) > 3 else ""
            
            # Guardar en base de datos
            add_appointment_db(user_id, title, datetime_str, alarm_offset, note)
            
            await update.message.reply_text(
                f"🎉 ¡Cita registrada!\n"
                f"<b>Evento:</b> {title}\n"
                f"<b>Fecha:</b> {datetime_str}\n"
                f"<b>Aviso:</b> {alarm_offset} min antes."
                , parse_mode="HTML"
            )
        except Exception as e:
            await update.message.reply_text(
                f"❌ Error al procesar la cita. Formato incorrecto. Por favor, inténtalo de nuevo usando /cita.\nDetalles: {e}"
            )
        return

    # 2. Gestión de límites diarios de IA
    usage = get_ia_usage(user_id)
    if usage >= 50:
        await update.message.reply_text("🚫 Has alcanzado tu límite diario de 50 mensajes para la IA. Se reiniciará mañana o mediante comando de administrador.")
        return
        
    # Incrementar uso diario
    increment_ia_usage(user_id)
    
    # Obtener respuesta de IA (preparado para Groq/OpenAI en utils.py)
    ai_response_text = get_ai_response(text)
    
    # 3. Síntesis de voz (Texto a Voz) utilizando gTTS y atempo (ffmpeg) mediante filtro
    lang_code = context.user_data.get("voice_lang", "es")
    tempo = context.user_data.get("voice_tempo", 1.0)
    
    # Generar archivo de audio temporal
    temp_tts_file = f"temp_tts_{user_id}_{int(time.time())}.mp3"
    temp_final_file = f"temp_final_{user_id}_{int(time.time())}.mp3"
    
    try:
        # Generar audio base con gTTS
        tts = gTTS(text=ai_response_text, lang=lang_code, slow=False)
        tts.save(temp_tts_file)
        
        # Aplicar control de velocidad real mediante ffmpeg y el filtro atempo
        # Nota: el filtro atempo acepta valores entre 0.5 y 2.0.
        os.system(f'ffmpeg -i {temp_tts_file} -filter:a "atempo={tempo}" -vn {temp_final_file} -y')
        
        # Enviar nota de voz a Telegram
        with open(temp_final_file, 'rb') as audio:
            await update.message.reply_voice(voice=audio, caption=ai_response_text)
            
    except Exception as e:
        logger.error(f"Error al procesar la nota de voz: {e}")
        await update.message.reply_text(f"IA: {ai_response_text}\n(Nota: Falló la síntesis de voz).")
        
    finally:
        # Limpieza de archivos temporales
        if os.path.exists(temp_tts_file):
            os.remove(temp_tts_file)
        if os.path.exists(temp_final_file):
            os.remove(temp_final_file)
