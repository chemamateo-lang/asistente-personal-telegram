from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

def get_compras_keyboard(compras):
    markup = InlineKeyboardMarkup(row_width=2)
    for item in compras:
        item_id = item[0]
        articulo = item[1]
        completado = item[2]
        estado = "✅" if completado else "❌"
        texto_boton = f"{estado} {articulo}"
        btn_toggle = InlineKeyboardButton(texto_boton, callback_data=f"toggle_{item_id}")
        btn_delete = InlineKeyboardButton("🗑️ Borrar", callback_data=f"delete_{item_id}")
        markup.add(btn_toggle, btn_delete)
    return markup

def get_preferencias_voz_keyboard(acento_actual, velocidad_actual):
    markup = InlineKeyboardMarkup(row_width=3)
    acentos = [('es', '🇪🇸 ES'), ('mx', '🇲🇽 MX'), ('ar', '🇦🇷 AR')]
    botones_acentos = []
    for val, label in acentos:
        prefix = "🟢 " if val == acento_actual else ""
        botones_acentos.append(InlineKeyboardButton(f"{prefix}{label}", callback_data=f"acento_{val}"))
    markup.add(*botones_acentos)
    
    velocidades = [(0.8, '🐢 0.8x'), (1.0, '▶️ 1.0x'), (1.2, '🐇 1.2x')]
    botones_velocidades = []
    for val, label in velocidades:
        prefix = "🟢 " if float(val) == float(velocidad_actual) else ""
        botones_velocidades.append(InlineKeyboardButton(f"{prefix}{label}", callback_data=f"vel_{val}"))
    markup.add(*botones_velocidades)
    return markup

def get_cita_opciones_keyboard(cita_id):
    """Teclado para gestionar una cita individual."""
    markup = InlineKeyboardMarkup(row_width=2)
    btn_notas = InlineKeyboardButton("📝 Notas", callback_data=f"cita_notas_{cita_id}")
    btn_alarmas = InlineKeyboardButton("⏰ Alarmas", callback_data=f"cita_alarmas_{cita_id}")
    btn_borrar = InlineKeyboardButton("🗑️ Borrar Cita", callback_data=f"cita_borrar_{cita_id}")
    
    markup.add(btn_notas, btn_alarmas)
    markup.add(btn_borrar)
    return markup

def get_lista_citas_keyboard(citas):
    """Crea un menú con botones para cada cita guardada."""
    markup = InlineKeyboardMarkup(row_width=1)
    for cita in citas:
        cita_id = cita[0]
        titulo = cita[1]
        fecha = cita[2]
        btn = InlineKeyboardButton(f"📅 {titulo} ({fecha})", callback_data=f"ver_cita_{cita_id}")
        markup.add(btn)
    return markup

def get_tareas_keyboard(tareas):
    """Crea un menú interactivo para gestionar tareas rápidas."""
    markup = InlineKeyboardMarkup(row_width=2)
    for item in tareas:
        item_id = item[0]
        texto = item[1]
        completado = item[2]
        estado = "✅" if completado else "❌"
        btn_toggle = InlineKeyboardButton(f"{estado} {texto}", callback_data=f"toggletarea_{item_id}")
        btn_delete = InlineKeyboardButton("🗑️ Borrar", callback_data=f"deletetarea_{item_id}")
        markup.add(btn_toggle, btn_delete)
    return markup

