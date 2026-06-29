from telegram import InlineKeyboardMarkup, InlineKeyboardButton


def get_compras_keyboard(compras: list) -> InlineKeyboardMarkup:
    rows = []
    for item_id, articulo, completado in compras:
        estado = "✅" if completado else "❌"
        rows.append([
            InlineKeyboardButton(f"{estado} {articulo}", callback_data=f"toggle_{item_id}"),
            InlineKeyboardButton("🗑️ Borrar", callback_data=f"delete_{item_id}"),
        ])
    return InlineKeyboardMarkup(rows)


def get_tareas_keyboard(tareas: list) -> InlineKeyboardMarkup:
    rows = []
    for item_id, texto, completado in tareas:
        estado = "✅" if completado else "❌"
        rows.append([
            InlineKeyboardButton(f"{estado} {texto}", callback_data=f"toggletarea_{item_id}"),
            InlineKeyboardButton("🗑️ Borrar", callback_data=f"deletetarea_{item_id}"),
        ])
    return InlineKeyboardMarkup(rows)


def get_lista_citas_keyboard(citas: list) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(f"📅 {titulo} ({fecha})", callback_data=f"ver_cita_{cita_id}")]
        for cita_id, titulo, fecha in citas
    ]
    return InlineKeyboardMarkup(rows)


def get_cita_opciones_keyboard(cita_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📝 Notas", callback_data=f"cita_notas_{cita_id}"),
            InlineKeyboardButton("⏰ Alarmas", callback_data=f"cita_alarmas_{cita_id}"),
        ],
        [InlineKeyboardButton("🗑️ Borrar Cita", callback_data=f"cita_borrar_{cita_id}")],
    ])


def get_preferencias_voz_keyboard(
    acento_actual: str, velocidad_actual: str, voz_activa: bool
) -> InlineKeyboardMarkup:
    acentos = [("es", "🇪🇸 ES"), ("mx", "🇲🇽 MX"), ("ar", "🇦🇷 AR")]
    velocidades = [
        ("0.8", "🐢 0.8x"),
        ("1.0", "▶️ 1.0x"),
        ("1.2", "🐇 1.2x"),
        ("1.5", "⚡ 1.5x"),
        ("2.0", "🚀 2.0x"),
    ]

    fila_acentos = [
        InlineKeyboardButton(
            f"{'🟢 ' if val == acento_actual else ''}{label}",
            callback_data=f"acento_{val}",
        )
        for val, label in acentos
    ]
    fila_velocidades = [
        InlineKeyboardButton(
            f"{'🟢 ' if val == velocidad_actual else ''}{label}",
            callback_data=f"vel_{val}",
        )
        for val, label in velocidades
    ]
    estado = "🔊 Voz activada" if voz_activa else "🔇 Voz desactivada"
    fila_toggle = [InlineKeyboardButton(estado, callback_data="toggle_voz")]

    return InlineKeyboardMarkup([fila_acentos, fila_velocidades, fila_toggle])
