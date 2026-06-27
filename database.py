import sqlite3
from config import DB_NAME

def get_connection():
    """Crea una conexión a la base de datos SQLite."""
    conn = sqlite3.connect(DB_NAME)
    # Habilitamos claves foráneas para que funcione el borrado en cascada (ON DELETE CASCADE)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_db():
    """Crea las tablas en la base de datos si no existen."""
    conn = get_connection()
    c = conn.cursor()
    
    # Tabla de usuarios / contadores de uso de IA
    c.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            user_id INTEGER PRIMARY KEY,
            usos_ia_hoy INTEGER DEFAULT 0,
            fecha_reset TEXT
        )
    ''')
    
    # Tabla de lista de la compra
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
            texto_tarea TEXT,
            completado INTEGER DEFAULT 0
        )
    ''')
    
    # Tabla de citas / agenda (Padre)
    c.execute('''
        CREATE TABLE IF NOT EXISTS citas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            titulo TEXT,
            fecha TEXT
        )
    ''')
    
    # Tabla de notas de citas (Hijo - se borra sola si se borra la cita padre)
    c.execute('''
        CREATE TABLE IF NOT EXISTS notas_citas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cita_id INTEGER,
            nota TEXT,
            FOREIGN KEY(cita_id) REFERENCES citas(id) ON DELETE CASCADE
        )
    ''')
    
    # Tabla de alarmas de citas (Hijo - se borra sola si se borra la cita padre)
    c.execute('''
        CREATE TABLE IF NOT EXISTS alarmas_citas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cita_id INTEGER,
            tiempo_alarma TEXT,
            FOREIGN KEY(cita_id) REFERENCES citas(id) ON DELETE CASCADE
        )
    ''')
    
    conn.commit()
    conn.close()

# ==========================================
# GESTIÓN DE USO DE IA
# ==========================================

def get_uso_ia_hoy(user_id):
    """Devuelve cuántas veces ha usado la IA el usuario hoy."""
    import datetime
    hoy_str = datetime.date.today().isoformat()
    
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT usos_ia_hoy, fecha_reset FROM usuarios WHERE user_id = ?", (user_id,))
    fila = c.fetchone()
    
    if not fila:
        c.execute("INSERT INTO usuarios (user_id, usos_ia_hoy, fecha_reset) VALUES (?, 0, ?)", (user_id, hoy_str))
        conn.commit()
        conn.close()
        return 0
        
    usos, fecha_reset = fila
    
    if fecha_reset != hoy_str:
        c.execute("UPDATE usuarios SET usos_ia_hoy = 0, fecha_reset = ? WHERE user_id = ?", (hoy_str, user_id))
        conn.commit()
        conn.close()
        return 0
        
    conn.close()
    return usos

def incrementar_uso_ia(user_id):
    """Suma 1 al contador de uso de IA del usuario hoy y devuelve el total actualizado."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("UPDATE usuarios SET usos_ia_hoy = usos_ia_hoy + 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    
    c.execute("SELECT usos_ia_hoy FROM usuarios WHERE user_id = ?", (user_id,))
    total = c.fetchone()[0]
    conn.close()
    return total

# ==========================================
# GESTIÓN DE LA LISTA DE LA COMPRA
# ==========================================

def get_compras(user_id):
    """Devuelve los ítems de la lista de la compra de un usuario."""
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
    c.execute("INSERT INTO compras (user_id, articulo, completado) VALUES (?, ?, 0)", (user_id, articulo))
    conn.commit()
    conn.close()

def toggle_compra(item_id):
    """Marca o desmarca un artículo como comprado."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("UPDATE compras SET completado = NOT completado WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()

def delete_compra(item_id):
    """Elimina un artículo de la lista de la compra."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM compras WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()

# ==========================================
# GESTIÓN DE TAREAS RÁPIDAS
# ==========================================

def add_tarea(user_id, texto_tarea):
    """Añade una tarea rápida a la lista del usuario."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("INSERT INTO tareas (user_id, texto_tarea, completado) VALUES (?, ?, 0)", (user_id, texto_tarea))
    conn.commit()
    conn.close()

def get_tareas_usuario(user_id):
    """Devuelve todas las tareas pendientes de un usuario."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT id, texto_tarea, completado FROM tareas WHERE user_id = ? ORDER BY id DESC", (user_id,))
    tareas = c.fetchall()
    conn.close()
    return tareas

def toggle_tarea(task_id):
    """Alterna el estado de completado de una tarea."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("UPDATE tareas SET completado = NOT completado WHERE id = ?", (task_id,))
    conn.commit()
    conn.close()

def delete_tarea(task_id):
    """Elimina una tarea rápida de la base de datos."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM tareas WHERE id = ?", (task_id,))
    conn.commit()
    conn.close()

# ==========================================
# GESTIÓN DE CITAS, ALARMAS Y NOTAS
# ==========================================

def add_cita(user_id, titulo, fecha):
    """Añade una cita a la agenda y devuelve su ID generado."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("INSERT INTO citas (user_id, titulo, fecha) VALUES (?, ?, ?)", (user_id, titulo, fecha))
    conn.commit()
    
    cita_id = c.lastrowid
    conn.close()
    return cita_id

def get_citas_usuario(user_id):
    """Devuelve todas las citas de un usuario ordenadas por ID descendente."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT id, titulo, fecha FROM citas WHERE user_id = ? ORDER BY id DESC", (user_id,))
    filas = c.fetchall()
    conn.close()
    return filas

def delete_cita(cita_id):
    """Elimina una cita de la base de datos y en cascada sus notas/alarmas."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM citas WHERE id = ?", (cita_id,))
    conn.commit()
    conn.close()

# --- Notas de citas ---

def add_nota(cita_id, nota_texto):
    """Añade una nota asociada a una cita específica."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("INSERT INTO notas_citas (cita_id, nota) VALUES (?, ?)", (cita_id, nota_texto))
    conn.commit()
    conn.close()

def get_notas_by_cita(cita_id):
    """Recupera todas las notas asociadas a una cita."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT id, nota FROM notas_citas WHERE cita_id = ?", (cita_id,))
    notas = c.fetchall()
    conn.close()
    return notas

# --- Alarmas de citas ---

def add_alarma(cita_id, tiempo_alarma):
    """Añade una alarma/aviso asociado a una cita específica."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("INSERT INTO alarmas_citas (cita_id, tiempo_alarma) VALUES (?, ?)", (cita_id, tiempo_alarma))
    conn.commit()
    conn.close()

def get_alarmas_by_cita(cita_id):
    """Recupera todas las alarmas asociadas a una cita."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT id, tiempo_alarma FROM alarmas_citas WHERE cita_id = ?", (cita_id,))
    alarmas = c.fetchall()
    conn.close()
    return alarmas
