"""
documentos.py — Archivo personal de documentos en el disco de la Raspberry.

Uso desde Telegram:
  - Envía (o reenvía) un PDF o cualquier archivo  -> el bot pregunta en qué carpeta guardarlo.
  - Envía una foto con el texto "doc" o "guardar" -> se guarda como documento (sin análisis IA).
  - /docs            -> elegir carpeta y ver sus documentos (pulsa uno para recibirlo).
  - /buscar <texto>  -> buscar documentos por nombre en todas las carpetas.

Los archivos se guardan SOLO en disco (DOCS_DIR), nunca en el repositorio.
Por privacidad, si ADMIN_USER_ID está configurado solo ese usuario puede usar el archivo.
"""

import datetime
import logging
import os
import re
import unicodedata
from pathlib import Path

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from config import ADMIN_USER_ID

logger = logging.getLogger(__name__)

# Carpeta raíz del archivo. Configúrala en .env apuntando al disco externo,
# por ejemplo: DOCS_DIR=/mnt/disco/documentos
DOCS_DIR = Path(os.getenv("DOCS_DIR", str(Path.home() / "documentos_bot"))).expanduser()

# clave interna -> nombre visible (la clave es también el nombre de la subcarpeta)
CARPETAS: dict[str, str] = {
    "serventia": "💼 Trabajo Serventia",
    "sepe_mateo": "🏛️ SEPE Mateo",
    "sepe_maribel": "🏛️ SEPE Maribel",
    "otros": "📁 Otros",
}

_MAX_LISTADO = 30          # documentos máximos mostrados por carpeta / búsqueda
_FOTO_CAPTION = re.compile(r"^\s*(doc|guardar)\b", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------

def _autorizado(update: Update) -> bool:
    return ADMIN_USER_ID is None or update.effective_user.id == ADMIN_USER_ID


def _nombre_seguro(nombre: str) -> str:
    """Quita rutas y caracteres problemáticos del nombre de archivo."""
    nombre = os.path.basename(nombre or "").strip()
    nombre = unicodedata.normalize("NFKD", nombre).encode("ascii", "ignore").decode()
    nombre = re.sub(r"[^A-Za-z0-9._ -]", "_", nombre).strip(" .")
    return nombre[:120] or "documento"


def _ruta_libre(carpeta: Path, nombre: str) -> Path:
    """Devuelve una ruta que no pise un archivo existente."""
    destino = carpeta / nombre
    base, ext = os.path.splitext(nombre)
    n = 2
    while destino.exists():
        destino = carpeta / f"{base}_{n}{ext}"
        n += 1
    return destino


def _listar(carpeta: str) -> list[Path]:
    ruta = DOCS_DIR / carpeta
    if not ruta.is_dir():
        return []
    return sorted((p for p in ruta.iterdir() if p.is_file()), reverse=True)


def _tam(p: Path) -> str:
    kb = p.stat().st_size / 1024
    return f"{kb / 1024:.1f} MB" if kb >= 1024 else f"{kb:.0f} KB"


def _teclado_carpetas(prefijo: str) -> InlineKeyboardMarkup:
    filas = [
        [InlineKeyboardButton(label, callback_data=f"{prefijo}_{clave}")]
        for clave, label in CARPETAS.items()
    ]
    if prefijo == "docsave":
        filas.append([InlineKeyboardButton("❌ No guardar", callback_data="docsave_cancelar")])
    return InlineKeyboardMarkup(filas)


def _teclado_archivos(rutas: list[Path]) -> InlineKeyboardMarkup:
    # callback_data máx. 64 bytes: usamos un índice guardado en user_data
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"📄 {p.name[:50]}", callback_data=f"docget_{i}")]
        for i, p in enumerate(rutas[:_MAX_LISTADO])
    ])


# ---------------------------------------------------------------------------
# Guardar
# ---------------------------------------------------------------------------

async def recibir_documento(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Archivo (PDF, etc.) recibido: pregunta en qué carpeta guardarlo."""
    if not _autorizado(update):
        return
    doc = update.message.document
    ctx.user_data["doc_pendiente"] = {
        "file_id": doc.file_id,
        "nombre": doc.file_name or "documento",
    }
    await update.message.reply_text(
        f"📥 *{doc.file_name or 'Documento'}*\n¿En qué carpeta lo guardo?",
        reply_markup=_teclado_carpetas("docsave"),
        parse_mode="Markdown",
    )


async def recibir_foto_doc(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Foto con texto 'doc'/'guardar': se archiva como documento."""
    if not _autorizado(update):
        return
    foto = update.message.photo[-1]
    resto = _FOTO_CAPTION.sub("", update.message.caption or "").strip()
    ctx.user_data["doc_pendiente"] = {
        "file_id": foto.file_id,
        "nombre": f"{resto or 'foto'}.jpg",
    }
    await update.message.reply_text(
        "📷 ¿En qué carpeta guardo la foto?",
        reply_markup=_teclado_carpetas("docsave"),
    )


async def callback_guardar(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if not _autorizado(update):
        return

    clave = query.data.removeprefix("docsave_")
    pendiente = ctx.user_data.pop("doc_pendiente", None)

    if clave == "cancelar":
        await query.edit_message_text("De acuerdo, no lo guardo.")
        return
    if not pendiente or clave not in CARPETAS:
        await query.edit_message_text("⚠️ No encuentro el documento. Vuelve a enviarlo.")
        return

    try:
        carpeta = DOCS_DIR / clave
        carpeta.mkdir(parents=True, exist_ok=True)
        fecha = datetime.date.today().isoformat()
        destino = _ruta_libre(carpeta, f"{fecha}_{_nombre_seguro(pendiente['nombre'])}")

        archivo = await ctx.bot.get_file(pendiente["file_id"])
        await archivo.download_to_drive(custom_path=destino)

        logger.info(f"Documento guardado: {destino}")
        await query.edit_message_text(
            f"✅ Guardado en *{CARPETAS[clave]}*\n`{destino.name}` ({_tam(destino)})",
            parse_mode="Markdown",
        )
    except Exception as e:
        logger.error(f"Error guardando documento: {e}")
        await query.edit_message_text(
            "❌ No he podido guardarlo. ¿Está el disco conectado?\n"
            f"Carpeta configurada: `{DOCS_DIR}`",
            parse_mode="Markdown",
        )


# ---------------------------------------------------------------------------
# Consultar
# ---------------------------------------------------------------------------

async def cmd_docs(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _autorizado(update):
        return
    resumen = "\n".join(
        f"{label}: {len(_listar(clave))}" for clave, label in CARPETAS.items()
    )
    await update.message.reply_text(
        f"🗂️ *Archivo de documentos*\n\n{resumen}\n\nElige una carpeta:",
        reply_markup=_teclado_carpetas("docver"),
        parse_mode="Markdown",
    )


async def callback_ver_carpeta(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if not _autorizado(update):
        return
    clave = query.data.removeprefix("docver_")
    rutas = _listar(clave)
    if not rutas:
        await query.edit_message_text(f"{CARPETAS.get(clave, clave)} está vacía.")
        return
    ctx.user_data["doc_resultados"] = [str(p) for p in rutas[:_MAX_LISTADO]]
    extra = f"\n(Mostrando los {_MAX_LISTADO} más recientes)" if len(rutas) > _MAX_LISTADO else ""
    await query.edit_message_text(
        f"{CARPETAS[clave]} — {len(rutas)} documentos{extra}\nPulsa uno para recibirlo:",
        reply_markup=_teclado_archivos(rutas),
    )


async def cmd_buscar(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _autorizado(update):
        return
    texto = " ".join(ctx.args).strip().lower()
    if not texto:
        await update.message.reply_text("Uso: /buscar <texto>   (ej: /buscar cuadrante)")
        return
    palabras = texto.split()
    encontrados = [
        p for clave in CARPETAS for p in _listar(clave)
        if all(w in p.name.lower() for w in palabras)
    ]
    if not encontrados:
        await update.message.reply_text(f"No encuentro documentos con «{texto}».")
        return
    encontrados.sort(key=lambda p: p.name, reverse=True)
    ctx.user_data["doc_resultados"] = [str(p) for p in encontrados[:_MAX_LISTADO]]
    await update.message.reply_text(
        f"🔎 {len(encontrados)} resultado(s) para «{texto}»:",
        reply_markup=_teclado_archivos(encontrados),
    )


async def callback_enviar(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if not _autorizado(update):
        return
    resultados = ctx.user_data.get("doc_resultados") or []
    idx = int(query.data.removeprefix("docget_"))
    if idx >= len(resultados):
        await query.message.reply_text("⚠️ Lista caducada. Vuelve a usar /docs o /buscar.")
        return
    ruta = Path(resultados[idx]).resolve()
    if DOCS_DIR.resolve() not in ruta.parents or not ruta.is_file():
        await query.message.reply_text("⚠️ Ese documento ya no existe.")
        return
    with ruta.open("rb") as f:
        await query.message.reply_document(document=f, filename=ruta.name)


# ---------------------------------------------------------------------------
# Registro
# ---------------------------------------------------------------------------

def registrar(app: Application) -> None:
    """Añade los handlers del archivo. Llamar ANTES del handler genérico de fotos."""
    app.add_handler(CommandHandler("docs", cmd_docs))
    app.add_handler(CommandHandler("buscar", cmd_buscar))
    app.add_handler(CallbackQueryHandler(callback_guardar, pattern=r"^docsave_\w+$"))
    app.add_handler(CallbackQueryHandler(callback_ver_carpeta, pattern=r"^docver_\w+$"))
    app.add_handler(CallbackQueryHandler(callback_enviar, pattern=r"^docget_\d+$"))
    app.add_handler(MessageHandler(filters.Document.ALL, recibir_documento))
    app.add_handler(MessageHandler(
        filters.PHOTO & filters.CaptionRegex(_FOTO_CAPTION), recibir_foto_doc
    ))
    logger.info(f"Archivo de documentos activo en {DOCS_DIR}")
