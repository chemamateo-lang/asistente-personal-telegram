import os
import logging
from openai import OpenAI
from config import OPENAI_API_KEY

logger = logging.getLogger(__name__)

openai_client = OpenAI(api_key=OPENAI_API_KEY)

# Mapeo de acentos a voces de OpenAI TTS
_VOZ_POR_ACENTO = {
    "es": "nova",
    "mx": "echo",
    "ar": "onyx",
}


def generar_audio_tts(texto: str, acento: str, velocidad: str, output_path: str) -> str | None:
    """Convierte texto a voz con OpenAI TTS. Devuelve output_path o None si falla."""
    voz = _VOZ_POR_ACENTO.get(acento, "alloy")
    try:
        response = openai_client.audio.speech.create(
            model="tts-1",
            voice=voz,
            input=texto,
            speed=float(velocidad),
        )
        response.stream_to_file(output_path)
        return output_path
    except Exception as e:
        logger.error(f"Error en OpenAI TTS: {e}")
        return None


def limpiar_archivos_temporales(*filepaths: str) -> None:
    """Elimina archivos temporales del disco."""
    for path in filepaths:
        if path and os.path.exists(path):
            try:
                os.remove(path)
            except Exception as e:
                logger.error(f"Error al eliminar archivo temporal {path}: {e}")
