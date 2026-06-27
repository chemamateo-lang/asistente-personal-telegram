# test_handlers.py
import logging
from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

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
