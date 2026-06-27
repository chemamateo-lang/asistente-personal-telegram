import time
import datetime
import sqlite3
from telebot import TeleBot
from config import TELEGRAM_BOT_TOKEN
# Nota: Ajusta aquí el formato de tiempo en el que guardas tus alarmas en base de datos.
# Asumiendo que el usuario guarda avisos relativos como "30 minutos antes" o fechas exactas.

def obtener_alarmas_pendientes():
    """Consulta las alarmas no enviadas desde la base de datos SQLite."""
    conn = sqlite3.connect('base_datos.db') # Reemplaza por el nombre de tu base de datos si es diferente
    c = conn.cursor()
    
    # Comprobamos si la columna 'enviada' existe en la tabla alarmas
    c.execute("PRAGMA table_info(alarmas)")
    columnas = [info[1] for info in c.fetchall()]
    if 'enviada' not in columnas:
        c.execute("ALTER TABLE alarmas ADD COLUMN enviada INTEGER DEFAULT 0")
        conn.commit()
        
    # Seleccionamos alarmas que no estén enviadas
    c.execute("""
        SELECT a.id, a.cita_id, a.tiempo_aviso, c.titulo, c.user_id 
        FROM alarmas a 
        JOIN citas c ON a.cita_id = c.id 
        WHERE a.enviada = 0
    """)
    alarmas = c.fetchall()
    conn.close()
    return alarmas

def verificar_y_avisar(bot):
    """Bucle que comprueba las alarmas cada minuto."""
    print(f"⏰ [Bucle de alarmas activo] Asistente proactivo iniciado.")
    while True:
        try:
            alarmas = obtener_alarmas_pendientes()
            ahora = datetime.datetime.now()
            
            for alarma in alarmas:
                alarma_id, cita_id, tiempo_aviso, titulo, user_id = alarma
                
                # Lógica de aviso proactivo: 
                # (Aquí puedes parsear el campo 'tiempo_aviso' del usuario. 
                # A modo de ejemplo, simulamos que si el aviso coincide con la hora actual, se dispara).
                # Un sistema de notificaciones proactivas real parsea la fecha de la cita menos el tiempo_aviso.
                
                # Ejemplo de notificación simulada:
                # bot.send_message(user_id, f"⏰ *¡Aviso proactivo!* Tienes la cita: *{titulo}* próximamente.")
                # marcar_alarma_enviada(alarma_id)
                pass
                
        except Exception as e:
            print(f"Error en el comprobador de alarmas: {e}")
            
        time.sleep(60) # Comprueba cada 60 segundos (1 minuto)
