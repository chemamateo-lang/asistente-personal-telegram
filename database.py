import sqlite3
import datetime
from config import DB_NAME

def get_connection():
    """Devuelve una conexión a la base de datos para entornos multihilo."""
    return sqlite3.connect(DB_NAME)

def init_db():
    """Inicializa y crea las tablas necesarias en SQLite."""
    conn = get_connection()
    c = conn.cursor()
    
    # 1. Tabla de Citas (Contenedor principal)
    c.execute('''CREATE TABLE IF NOT EXISTS citas (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    titulo TEXT,
                    fecha TEXT
                )''')
    
    # 2. Tabla de Alarmas (Múltiples alarmas por cita)
    c.execute('''CREATE TABLE IF NOT EXISTS alarmas (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cita_id INTEGER,
                    fecha_hora TEXT,
                    notificado INTEGER DEFAULT 0,
                    FOREIGN KEY(cita_id) REFERENCES citas(id) ON DELETE CASCADE
                )''')
    
    # 3. Tabla de Notas (Múltiples notas por cita, editables/borrables individualmente)
    c.execute('''CREATE TABLE IF NOT EXISTS notas (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cita_id INTEGER,
                    contenido TEXT,
                    FOREIGN KEY(cita_id) REFERENCES citas(id) ON DELETE CASCADE
                )''')
    
    # 4. Tabla de la Lista de la Compra
    c.execute('''CREATE TABLE IF NOT EXISTS compras (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    articulo TEXT,
                    completado INTEGER DEFAULT 0
                )''')
    
    # 5. Control de Uso de IA (Para el chivato diario)
    c.execute('''CREATE TABLE IF NOT EXISTS uso_ia (
                    user_id INTEGER,
                    fecha TEXT,
                    contador INTEGER DEFAULT 0,
                    PRIMARY KEY (user_id, fecha)
                )''')
    
    # 6. Preferencias de Voz
    c.execute('''CREATE TABLE IF NOT EXISTS preferencias_voz (
                    user_id INTEGER PRIMARY KEY,
                    acento TEXT DEFAULT 'es',
                    velocidad REAL DEFAULT 1.0
                )''')
    
    conn.commit()
    conn.close()

# ==========================================
# GESTIÓN DE CITAS, ALARMAS Y NOTAS
# ==========================================

def add_cita(user_id, titulo, fecha):
    """Crea una cita nueva y devuelve su ID generado."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("INSERT INTO citas (user_id, titulo, fecha) VALUES (?, ?, ?)", (user_id, titulo, fecha))
    conn.commit()
    nuevo_id = c.lastrowid
    conn.close()
    return nuevo_id

def add_alarma(cita_id, fecha_hora):
    """Añade una alarma asociada a una cita."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("INSERT INTO alarmas (cita_id, fecha_hora, notificado) VALUES (?, ?, 0)", (cita_id, fecha_hora))
    conn.commit()
    conn.close()

def add_nota(cita_id, contenido):
    """Añade una nota asociada a una cita."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("INSERT INTO notas (cita_id, contenido) VALUES (?, ?)", (cita_id, contenido))
    conn.commit()
    conn.close()

def get_notas_by_cita(cita_id):
    """Recupera todas las notas de una cita concreta."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT id, contenido FROM notas WHERE cita_id = ?", (cita_id,))
    notas = c.fetchall()
    conn.close()
    return notas

def edit_nota(nota_id, nuevo_contenido):
    """Actualiza el contenido de una nota específica sin alterar otras notas."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("UPDATE notas SET contenido = ? WHERE id = ?", (nuevo_contenido, nota_id))
    conn.commit()
    conn.close()

def delete_nota(nota_id):
    """Elimina una nota específica."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM notas WHERE id = ?", (nota_id,))
    conn.commit()
    conn.close()

# ==========================================
# GESTIÓN DE LA LISTA DE LA COMPRA
# ==========================================

def add_compra(user_id, articulo):
    conn = get_connection()
    c = conn.cursor()
    c.execute("INSERT INTO compras (user_id, articulo) VALUES (?, ?)", (user_id, articulo))
    conn.commit()
    conn.close()

def get_compras(user_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT id, articulo, completado FROM compras WHERE user_id = ?", (user_id,))
    items = c.fetchall()
    conn.close()
    return items

def toggle_compra(item_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("UPDATE compras SET completado = CASE WHEN completado = 1 THEN 0 ELSE 1 END WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()

def delete_compra(item_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM compras WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()

# ==========================================
# CONTROL DE USO DE IA
# ==========================================

def get_uso_ia_hoy(user_id):
    hoy = datetime.date.today().strftime("%Y-%m-%d")
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT contador FROM uso_ia WHERE user_id = ? AND fecha = ?", (user_id, hoy))
    resultado = c.fetchone()
    conn.close()
    return resultado[0] if resultado else 0

def incrementar_uso_ia(user_id):
    hoy = datetime.date.today().strftime("%Y-%m-%d")
    conn = get_connection()
    c = conn.cursor()
    uso_actual = get_uso_ia_hoy(user_id)
    
    if uso_actual == 0:
        c.execute("INSERT INTO uso_ia (user_id, fecha, contador) VALUES (?, ?, 1)", (user_id, hoy))
    else:
        c.execute("UPDATE uso_ia SET contador = contador + 1 WHERE user_id = ? AND fecha = ?", (user_id, hoy))
    
    conn.commit()
    conn.close()
    return uso_actual + 1

# ==========================================
# PREFERENCIAS DE VOZ
# ==========================================

def get_preferencias_voz(user_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT acento, velocidad FROM preferencias_voz WHERE user_id = ?", (user_id,))
    resultado = c.fetchone()
    conn.close()
    return resultado if resultado else ('es', 1.0)

def set_preferencia_voz(user_id, acento=None, velocidad=None):
    conn = get_connection()
    c = conn.cursor()
    
    actual = get_preferencias_voz(user_id)
    nuevo_acento = acento if acento else actual[0]
    nueva_velocidad = velocidad if velocidad else actual[1]
    
    c.execute("""
        INSERT INTO preferencias_voz (user_id, acento, velocidad) 
        VALUES (?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET acento=excluded.acento, velocidad=excluded.velocidad
    """, (user_id, nuevo_acento, nueva_velocidad))
    
    conn.commit()
    conn.close()
