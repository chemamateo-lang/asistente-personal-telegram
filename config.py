import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ADMIN_USER_ID = int(os.getenv("ADMIN_USER_ID", "0"))

DB_NAME = "bot_database.sqlite"
LIMITE_IA_DIARIO = 20
