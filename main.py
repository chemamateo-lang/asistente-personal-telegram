# main.py
import logging
import os
from dotenv import load_dotenv
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from alarm_checker import start_alarm_checker  # Módulo proactivo de alarmas en segundo plano
from database import init_db
from handlers import start, set_voice_settings, reset_ia, cita_command, test_command, test_echo, button_handler, handle_message

# Carga las variables de entorno desde el fichero .env
load_dotenv()

# Configuración de los logs
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Token del bot de Telegram obtenido de forma segura desde el archivo .env
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

def main() -> None:
    """Función principal de inicialización y arranque del bot."""
    logger.info("Inicializando base de datos...")
    init_db()

    logger.info("Iniciando hilo proactivo de comprobación de alarmas...")
    start_alarm_checker()

    logger.info("Construyendo la aplicación de Telegram...")
    
    if not TOKEN:
        logger.error("No se ha encontrado el token del bot en las variables de entorno (.env). Saliendo...")
        return

    application = ApplicationBuilder().token(TOKEN).build()

    # --- Registro de Handlers ---
    
    # Comandos principales y de configuración
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("voz", set_voice_settings))
    application.add_handler(CommandHandler("reset_ia", reset_ia))
    application.add_handler(CommandHandler("cita", cita_command))
    
    # Comandos de pruebas / simulación
    application.add_handler(CommandHandler("test", test_command))
    application.add_handler(CommandHandler("echo", test_echo))
    
    # Manejador de botones interactivos (Inline Keyboards)
    application.add_handler(CallbackQueryHandler(button_handler))
    
    # Manejador de mensajes de texto (para IA, asistente paso a paso, etc.)
    # Se aplican filtros para evitar que procese comandos como mensajes normales
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Iniciando el bot... (Pulsa Ctrl+C para salir)")
    
    # Arrancar el bot en modo polling (se adapta para despliegue con PM2)
    application.run_polling()

if __name__ == '__main__':
    main()
