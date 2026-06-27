import os
from telebot import TeleBot
from config import BOT_TOKEN
from handlers import registrar_handlers

bot = TeleBot(BOT_TOKEN)
registrar_handlers(bot)

if __name__ == '__main__':
    print("🤖 Iniciando bot modular...")
    bot.remove_webhook()
    bot.infinity_polling()
