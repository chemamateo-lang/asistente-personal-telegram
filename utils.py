import os
from groq import Groq
from openai import OpenAI
from config import GROQ_API_KEY, OPENAI_API_KEY

# Inicialización de clientes para IA
groq_client = Groq(api_key=GROQ_API_KEY)
openai_client = OpenAI(api_key=OPENAI_API_KEY)

# ==========================================
# 1. INTEGRACIÓN GROQ (LLM - Texto)
# ==========================================

def generar_respuesta_texto(prompt, system_prompt="Eres un asistente personal útil, sencillo e intuitivo."):
    """Genera respuestas de texto usando Llama-3.3-70b a través de Groq."""
    try:
        chat_completion = groq_client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.7,
        )
        return chat_completion.choices[0].message.content
    except Exception as e:
        print(f"Error en Groq LLM: {e}")
        return "Lo siento, tuve un problema procesando tu petición en texto."

# ==========================================
# 2. INTEGRACIÓN GROQ (WHISPER - STT / Voz a Texto)
# ==========================================

def transcribir_audio(file_path):
    """Transcribe un archivo de voz utilizando Whisper en Groq."""
    try:
        with open(file_path, "rb") as audio_file:
            transcription = groq_client.audio.transcriptions.create(
                file=audio_file,
                model="whisper-large-v3",
                response_format="text",
                language="es"  # Forzamos español para mayor precisión
            )
        return transcription
    except Exception as e:
        print(f"Error en Groq Whisper: {e}")
        return None

# ==========================================
# 3. INTEGRACIÓN OPENAI (TTS - Texto a Voz)
# ==========================================

def generar_audio_tts(texto, acento, velocidad, output_path):
    """
    Convierte texto a voz utilizando el modelo tts-1 de OpenAI.
    Mapea los acentos ('es', 'mx', 'ar') a diferentes voces preconfiguradas.
    """
    # Mapeo de acentos a voces de OpenAI
    voces = {
        'es': 'nova',   # Voz femenina clara y neutra
        'mx': 'echo',   # Voz masculina neutra
        'ar': 'onyx'    # Voz masculina un poco más profunda
    }
    
    voz_seleccionada = voces.get(acento, 'alloy')
    
    try:
        response = openai_client.audio.speech.create(
            model="tts-1",
            voice=voz_seleccionada,
            input=texto,
            speed=float(velocidad)
        )
        
        # Guarda el archivo de audio directamente en la ruta especificada
        response.stream_to_file(output_path)
        return output_path
    except Exception as e:
        print(f"Error en OpenAI TTS: {e}")
        return None

# ==========================================
# 4. UTILIDADES GENERALES
# ==========================================

def limpiar_archivos_temporales(*filepaths):
    """Elimina de disco los archivos temporales (como notas de audio) para liberar espacio."""
    for path in filepaths:
        if path and os.path.exists(path):
            try:
                os.remove(path)
            except Exception as e:
                print(f"Error al eliminar el archivo temporal {path}: {e}")
