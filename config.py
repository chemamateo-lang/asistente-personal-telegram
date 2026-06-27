import os
from dotenv import load_dotenv

# Carga las variables definidas en el archivo .env
load_dotenv()

# Cargar las claves desde el archivo .env de forma segura
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Verificación opcional para evitar arrancar el bot sin credenciales
if not GROQ_API_KEY:
    print("⚠️ Advertencia: La variable GROQ_API_KEY no está configurada en el archivo .env")
if not OPENAI_API_KEY:
    print("⚠️ Advertencia: La variable OPENAI_API_KEY no está configurada en el archivo .env")
