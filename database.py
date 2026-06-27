import sqlite3
import datetime

def get_connection():
    """Crea y devuelve una conexión a la base de datos SQLite."""
    conn = sqlite3.connect('base_datos.db')
    return conn

def init_db():
    """Inicializa y crea las tablas necesarias para el funcionamiento del bot si no existen."""
    conn = get_connection()
    c = conn.cursor()
    
    # Tabla de usuarios (para límites de IA y preferencias de voz)
    c.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            user_id INTEGER PRIMARY KEY,
            uso_ia_hoy INTEGER DEFAULT 0,
            fecha_uso_ia TEXT,
            acento TEXT DEFAULT 'es',
            velocidad TEXT DEFAULT '1.0'
        )
    ''')
    
    # Tabla de la lista de la compra
    c.execute('''
        CREATE TABLE IF NOT EXISTS compras (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            articulo TEXT,
            completado INTEGER DEFAULT 0
        )
    ''')
    
    # Tabla de tareas rápidas
    c.execute('''
        CREATE TABLE IF NOT EXISTS tareas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            texto TEXT,
            completado INTEGER DEFAULT 0
        )
    ''')
    
    # Tabla de citas / agenda
    c.execute('''
        CREATE TABLE IF NOT EXISTS citas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            titulo TEXT,
            fecha TEXT
        )
    ''')
    
    # Tabla de notas asociadas a las citas
    c.execute('''
        CREATE TABLE IF NOT EXISTS notas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cita_id INTEGER,
            texto_nota TEXT,
            FOREIGN KEY(cita_id) REFERENCES citas(id) ON DELETE CASCADE
        )
    ''')
    
    # Tabla de alarmas asociadas a las citas (con columna 'enviada' para avisos proactivos)
    c.execute('''
        CREATE TABLE IF NOT EXISTS alarmas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cita_id INTEGER,
            tiempo_aviso TEXT,
            enviada INTEGER DEFAULT 0,
            FOREIGN KEY(cita_id) REFERENCES citas(id) ON DELETE CASCADE
        )
    ''')
    
    conn.commit()
    conn.close()

# ------------------------------------------
# GESTIÓN DE USO DE IA Y LÍMITES
# ------------------------------------------

def get_uso_ia_hoy(user_id):
    """Devuelve cuántas veces ha usado la IA el usuario hoy."""
    conn = get_connection()
    c = conn.cursor()
    hoy = datetime.date.today().isoformat()
    
    c.execute("SELECT uso_ia_hoy, fecha_uso_ia FROM usuarios WHERE user_id = ?", (user_id,))
    fila = c.fetchone()
    
    if not fila:
        c.execute("INSERT INTO usuarios (user_id, uso_ia_hoy, fecha_uso_ia) VALUES (?, 0, ?)", (user_id, hoy))
        conn.commit()
        conn.close()
        return 0
        
    uso, fecha = fila
    if fecha != hoy:
        c.execute("UPDATE usuarios SET uso_ia_hoy = 0, fecha_uso_ia = ? WHERE user_id = ?", (hoy, user_id))
        conn.commit()
        conn.close()
        return 0
        
    conn.close()
    return uso

def incrementar_uso_ia(user_id):
    """Incrementa en 1 el contador de uso de la IA del usuario en el día actual."""
    conn = get_connection()
    c = conn.cursor()
    hoy = datetime.date.today().isoformat()
    
    # Nos aseguramos de inicializar el día correctamente
    get_uso_ia_hoy(user_id)
    
    c.execute("UPDATE usuarios SET uso_ia_hoy = uso_ia_hoy + 1 WHERE user_id = ?", (user_id,))
    c.execute("SELECT uso_ia_hoy FROM usuarios WHERE user_id = ?", (user_id,))
    nuevo_valor = c.fetchone()[0]
    
    conn.commit()
    conn.close()
    return nuevo_valor

# ------------------------------------------
# GESTIÓN DE LA LISTA DE LA COMPRA
# ------------------------------------------

def get_compras(user_id):
    """Devuelve los artículos de la compra de un usuario."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT id, articulo, completado FROM compras WHERE user_id = ?", (user_id,))
    items = c.fetchall()
    conn.close()
    return items

def add_compra(user_id, articulo):
    """Añade un artículo a la lista de la compra."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("INSERT INTO compras (user_id, articulo) VALUES (?, ?)", (user_id, articulo))
    conn.commit()
    conn.close()

def toggle_compra(item_id):
    """Alterna el estado de un artículo (marcado/desmarcado)."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("UPDATE compras SET completado = NOT completado WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()

def delete_compra(item_id):
    """Elimina un artículo de la lista."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM compras WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()

# ------------------------------------------
# GESTIÓN DE TAREAS RÁPIDAS
# ------------------------------------------

def get_tareas_usuario(user_id):
    """Devuelve todas las tareas rápidas de un usuario."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT id, texto, completado FROM tareas WHERE user_id = ?", (user_id,))
    tareas = c.fetchall()
    conn.close()
    return tareas

def add_tarea(user_id, texto):
    """Añade una tarea a la lista."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("INSERT INTO tareas (user_id, texto) VALUES (?, ?)", (user_id, texto))
    conn.commit()
    conn.close()

def toggle_tarea(item_id):
    """Alterna el estado de una tarea (completada/pendiente)."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("UPDATE tareas SET completado = NOT completado WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()

def delete_tarea(item_id):
    """Elimina una tarea de la base de datos."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM tareas WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()

# ------------------------------------------
# GESTIÓN DE CITAS Y AGENDA
# ------------------------------------------

def get_citas_usuario(user_id):
    """Devuelve todas las citas de un usuario."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT id, titulo, fecha FROM citas WHERE user_id = ? ORDER BY id DESC", (user_id,))
    citas = c.fetchall()
    conn.close()
    return citas

def add_cita(user_id, titulo, fecha):
    """Añade una cita y devuelve su ID generado."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("INSERT INTO citas (user_id, titulo, fecha) VALUES (?, ?, ?)", (user_id, titulo, fecha))
    conn.commit()
    
    # Obtenemos el ID de la cita recién insertada
    c.execute("SELECT last_insert_rowid()")
    cita_id = c.fetchone()[0]
    
    conn.close()
    return cita_id

def delete_cita(cita_id):
    """Elimina una cita, sus notas y sus alarmas."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM citas WHERE id = ?", (cita_id,))
    c.execute("DELETE FROM notas WHERE cita_id = ?", (cita_id,))
    c.execute("DELETE FROM alarmas WHERE cita_id = ?", (cita_id,))
    conn.commit()
    conn.close()

# ------------------------------------------
# GESTIÓN DE NOTAS DE CITAS
# ------------------------------------------

def get_notas_by_cita(cita_id):
    """Devuelve las notas asociadas a una cita."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT id, texto_nota FROM notas WHERE cita_id = ?", (cita_id,))
    notas = c.fetchall()
    conn.close()
    return notas

def add_nota(cita_id, texto_nota):
    """Añade una nota a una cita específica."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("INSERT INTO notas (cita_id, texto_nota) VALUES (?, ?)", (cita_id, texto_nota))
    conn.commit()
    conn.close()

# ------------------------------------------
# GESTIÓN DE ALARMAS Y AVISOS PROACTIVOS
# ------------------------------------------

def get_alarmas_by_cita(cita_id):
    """Devuelve las alarmas configuradas para una cita."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT id, tiempo_aviso, enviada FROM alarmas WHERE cita_id = ?", (cita_id,))
    alarmas = c.fetchall()
    conn.close()
    return alarmas

def add_alarma(cita_id, tiempo_aviso):
    """Añade una alarma o aviso para una cita."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("INSERT INTO alarmas (cita_id, tiempo_aviso, enviada) VALUES (?, ?, 0)", (cita_id, tiempo_aviso))
    conn.commit()
    conn.close()

def get_alarmas_pendientes():
    """Consulta las alarmas no enviadas desde la base de datos."""
    conn = get_connection()
    c = conn.cursor()
    # Seleccionamos alarmas activas que aún no hayan sido enviadas
    c.execute("""
        SELECT a.id, a.cita_id, a.tiempo_aviso, c.titulo, c.user_id 
        FROM alarmas a 
        JOIN citas c ON a.cita_id = c.id 
        WHERE a.enviada = 0
    """)
    alarmas = c.fetchall()
    conn.close()
    return alarmas

def marcar_alarma_enviada(alarma_id):
    """Marca una alarma como enviada para no repetir la notificación."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("UPDATE alarmas SET enviada = 1 WHERE id = ?", (alarma_id,))
    conn.commit()
    conn.close()

# ------------------------------------------
# PREFERENCIAS DE VOZ DEL USUARIO
# ------------------------------------------

def get_preferencias_voz(user_id):
    """Recupera las preferencias de voz (acento y velocidad) del usuario."""
    conn = get_connection()
    c = conn.cursor()
    
    # Verificamos si el usuario tiene columnas de voz en la tabla usuarios (por si migraciones anteriores)
    c.execute("PRAGMA table_info(usuarios)")
    columnas = [info[1] for info in c.fetchall()]
    
    if 'acento' not in columnas:
        c.execute("ALTER TABLE usuarios ADD COLUMN acento TEXT DEFAULT 'es'")
        c.execute("ALTER TABLE usuarios ADD COLUMN velocidad TEXT DEFAULT '1.0'")
        conn.commit()
        
    c.execute("SELECT acento, velocidad FROM usuarios WHERE user_id = ?", (user_id,))
    fila = c.fetchone()
    conn.close()
    
    if fila and fila[0]:
        return fila[0], fila[1]
    return 'es', '1.0'

def update_acento(user_id, acento):
    """Actualiza el acento preferido del usuario."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("UPDATE usuarios SET acento = ? WHERE user_id = ?", (acento, user_id))
    conn.commit()
    conn.close()

def update_velocidad(user_id, velocidad):
    """Actualiza la velocidad preferida del usuario."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("UPDATE usuarios SET velocidad = ? WHERE user_id = ?", (velocidad, user_id))
    conn.commit()
    conn.close()
