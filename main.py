import os
from telebot import TeleBot
from config import BOT_TOKEN
from handlers import registrar_handlers

# Inicializamos el bot de Telegram con el token
bot = TeleBot(BOT_TOKEN)

# Registramos todos los comandos y lógica desde handlers.py
registrar_handlers(bot)

if __name__ == '__main__':
    print("🤖 Iniciando bot modular...")
    # Quitamos eventuales bloqueos previos e iniciamos el pooling
    bot.remove_webhook()
    bot.infinity_polling()
