import os
import datetime
from telebot import TeleBot
from config import ADMIN_USER_ID, LIMITE_IA_DIARIO
import database
import utils
import keyboards

# Diccionario temporal global para guardar los pasos de creación de citas
user_cita_temp = {}

def registrar_handlers(bot: TeleBot):
    """Registra todos los comandos y mensajes interactivos del bot."""

    # Inicializar la base de datos al arrancar
    database.init_db()

    # ------------------------------------------
    # COMANDO INICIAL /START
    # ------------------------------------------
    @bot.message_handler(commands=['start'])
    def send_welcome(message):
        nombre = message.from_user.first_name
        bot.reply_to(message, f"¡Hola {nombre}! Soy tu asistente personal de IA. Estoy listo para ayudarte a gestionar tu agenda, listas y conversar. ¡Pruébame!")

    # ------------------------------------------
    # COMANDOS DE AYUDA Y MENÚ
    # ------------------------------------------
    @bot.message_handler(commands=['ayuda', 'menu'])
    def mostrar_ayuda(message):
        """Muestra la lista completa de comandos y funcionalidades del bot."""
        texto_ayuda = (
            "🤖 *¡Hola! Aquí tienes el menú de ayuda y los comandos disponibles:*\n\n"
            "📌 *Módulo de Agenda y Citas*\n"
            "• `/cita` ‑ Inicia el asistente interactivo paso a paso para crear un evento.\n"
            "• `/agenda` ‑ Muestra un listado de tus citas guardadas. Permite gestionarlas, añadir notas, alarmas o borrarlas.\n\n"
            "📝 *Módulo de Tareas Rápidas*\n"
            "• `/tarea <texto>` ‑ Añade una tarea rápida a tus pendientes.\n"
            "• `/pendientes` ‑ Muestra tu lista de tareas interactivas.\n\n"
            "🛒 *Módulo de Lista de la Compra*\n"
            "• `/comprar` ‑ Muestra tu lista de la compra interactiva (marca o borra artículos).\n"
            "• `/lista <artículo>` ‑ Añade directamente un producto a la lista.\n\n"
            "🤖 *Interacción con la IA*\n"
            "• Escribe cualquier mensaje directamente (sin barras) para conversar con la IA integrada.\n\n"
            "⚙️ *Sistema*\n"
            "• `/start` ‑ Mensaje de bienvenida.\n"
            "• `/ayuda` o `/menu` ‑ Muestra este mismo listado."
        )
        bot.reply_to(message, texto_ayuda, parse_mode="Markdown")

    # ------------------------------------------
    # GESTIÓN DE LA LISTA DE LA COMPRA
    # ------------------------------------------
    @bot.message_handler(commands=['comprar'])
    def ver_lista_compra(message):
        user_id = message.from_user.id
        items = database.get_compras(user_id)
        
        if not items:
            bot.reply_to(message, "Tu lista de la compra está vacía. Añade artículos escribiendo: */lista manzana*", parse_mode="Markdown")
        else:
            markup = keyboards.get_compras_keyboard(items)
            bot.reply_to(message, "🛒 *Tu Lista de la Compra*:", reply_markup=markup, parse_mode="Markdown")

    @bot.message_handler(commands=['lista'])
    def agregar_a_compra(message):
        user_id = message.from_user.id
        articulo = message.text.replace('/lista', '').strip()
        
        if not articulo:
            bot.reply_to(message, "Por favor, indica qué quieres añadir. Ejemplo: `/lista leche`")
            return
            
        database.add_compra(user_id, articulo)
        bot.reply_to(message, f"✅ Añadido a la compra: *{articulo}*", parse_mode="Markdown")

    @bot.callback_query_handler(func=lambda call: call.data.startswith('toggle_') or call.data.startswith('delete_'))
    def callback_compra(call):
        accion, item_id_str = call.data.split('_')
        item_id = int(item_id_str)
        
        if accion == 'toggle':
            database.toggle_compra(item_id)
        elif accion == 'delete':
            database.delete_compra(item_id)
            
        user_id = call.from_user.id
        items = database.get_compras(user_id)
        markup = keyboards.get_compras_keyboard(items)
        
        try:
            bot.edit_message_reply_markup(
                chat_id=call.message.chat.id, 
                message_id=call.message.message_id, 
                reply_markup=markup
            )
            bot.answer_callback_query(call.id, "¡Actualizado!")
        except Exception as e:
            print(f"Error al actualizar teclado de compra: {e}")

    # ------------------------------------------
    # GESTIÓN DE TAREAS RÁPIDAS
    # ------------------------------------------
    @bot.message_handler(commands=['tarea'])
    def agregar_tarea(message):
        user_id = message.from_user.id
        tarea_texto = message.text.replace('/tarea', '').strip()
        
        if not tarea_texto:
            bot.reply_to(message, "Por favor, indica la tarea que deseas agregar. Ejemplo: `/tarea regar las plantas`", parse_mode="Markdown")
            return
            
        database.add_tarea(user_id, tarea_texto)
        bot.reply_to(message, f"✅ Tarea agregada: *{tarea_texto}*", parse_mode="Markdown")

    @bot.message_handler(commands=['pendientes'])
    def ver_tareas(message):
        user_id = message.from_user.id
        tareas = database.get_tareas_usuario(user_id)
        
        if not tareas:
            bot.reply_to(message, "🎉 ¡No tienes tareas pendientes! Añade una escribiendo: `/tarea [texto]`", parse_mode="Markdown")
        else:
            markup = keyboards.get_tareas_keyboard(tareas)
            bot.reply_to(message, "📝 *Tus Tareas Pendientes*:", reply_markup=markup, parse_mode="Markdown")

    @bot.callback_query_handler(func=lambda call: call.data.startswith('toggletarea_') or call.data.startswith('deletetarea_'))
    def callback_tarea(call):
        accion, item_id_str = call.data.split('_')
        item_id = int(item_id_str)
        
        if accion == 'toggletarea':
            database.toggle_tarea(item_id)
        elif accion == 'deletetarea':
            database.delete_tarea(item_id)
            
        user_id = call.from_user.id
        tareas = database.get_tareas_usuario(user_id)
        markup = keyboards.get_tareas_keyboard(tareas)
        
        try:
            bot.edit_message_reply_markup(
                chat_id=call.message.chat.id, 
                message_id=call.message.message_id, 
                reply_markup=markup
            )
            bot.answer_callback_query(call.id, "¡Actualizado!")
        except Exception as e:
            print(f"Error al actualizar teclado de tareas: {e}")

    # ------------------------------------------
    # GESTIÓN DE CITAS Y AGENDA
    # ------------------------------------------
    
    @bot.message_handler(commands=['agenda'])
    def ver_agenda(message):
        """Muestra la lista de citas guardadas del usuario."""
        user_id = message.from_user.id
        citas = database.get_citas_usuario(user_id)
        
        if not citas:
            bot.reply_to(message, "📅 No tienes ninguna cita programada.\nPuedes crear una nueva escribiendo `/cita`.", parse_mode="Markdown")
        else:
            markup = keyboards.get_lista_citas_keyboard(citas)
            bot.reply_to(message, "📌 *Tus Citas Guardadas*:\nSelecciona una cita para ver sus opciones (notas, borrar, etc.):", reply_markup=markup, parse_mode="Markdown")

    @bot.message_handler(commands=['cita'])
    def cmd_nueva_cita(message):
        msg = bot.reply_to(message, "📝 Vamos a crear una nueva cita.\n\n¿Cuál es el *título* o asunto?", parse_mode="Markdown")
        bot.register_next_step_handler(msg, process_titulo)

    def process_titulo(message):
        chat_id = message.chat.id
        user_cita_temp[chat_id] = {'titulo': message.text}
        
        msg = bot.reply_to(message, "📅 Perfecto. Ahora dime la *fecha* (ej: 30-06-2026, Mañana, etc.):", parse_mode="Markdown")
        bot.register_next_step_handler(msg, process_fecha)

    def process_fecha(message):
        chat_id = message.chat.id
        user_id = message.from_user.id
        titulo = user_cita_temp[chat_id]['titulo']
        fecha = message.text
        
        cita_id = database.add_cita(user_id, titulo, fecha)
        del user_cita_temp[chat_id]
        
        markup = keyboards.get_cita_opciones_keyboard(cita_id)
        
        mensaje_confirmacion = (
            f"✅ *Cita guardada correctamente*\n\n"
            f"📌 *Asunto:* {titulo}\n"
            f"📅 *Fecha:* {fecha}\n\n"
            f"¿Qué más quieres hacer con esta cita?"
        )
        bot.reply_to(message, mensaje_confirmacion, reply_markup=markup, parse_mode="Markdown")

    # ------------------------------------------
    # MANEJADOR DE ACCIONES EN LÍNEA DE CITAS (Ver, Notas, Alarmas, Borrar)
    # ------------------------------------------
    
    @bot.callback_query_handler(func=lambda call: call.data.startswith('ver_cita_'))
    def callback_ver_cita(call):
        cita_id = int(call.data.split('_')[2])
        markup = keyboards.get_cita_opciones_keyboard(cita_id)
        bot.send_message(
            call.message.chat.id, 
            "⚙️ ¿Qué deseas gestionar de esta cita?", 
            reply_markup=markup
        )

    @bot.callback_query_handler(func=lambda call: call.data.startswith('cita_'))
    def callback_cita_opciones(call):
        partes = call.data.split('_')
        accion = partes[1]  # 'notas', 'alarmas' o 'borrar'
        cita_id = int(partes[2])
        
        if accion == 'borrar':
            database.delete_cita(cita_id)
            bot.edit_message_text(
                "🗑️ *Cita eliminada correctamente* junto con sus notas y alarmas.", 
                chat_id=call.message.chat.id, 
                message_id=call.message.message_id,
                parse_mode="Markdown"
            )
            
        elif accion == 'notas':
            notas = database.get_notas_by_cita(cita_id)
            
            if not notas:
                msg = bot.send_message(call.message.chat.id, "No hay notas para esta cita.\n\nEscribe ahora la nueva nota que quieres añadir (o escribe 'cancelar'):")
            else:
                texto_notas = "📝 *Notas actuales:*\n\n"
                for n in notas:
                    texto_notas += f"• {n[1]}\n"
                
                texto_notas += "\nEscribe una nueva nota para añadirla a la lista (o escribe 'cancelar'):"
                msg = bot.send_message(call.message.chat.id, texto_notas, parse_mode="Markdown")
            
            bot.register_next_step_handler(msg, process_add_nota, cita_id)

        elif accion == 'alarmas':
            alarmas = database.get_alarmas_by_cita(cita_id)
            
            if not alarmas:
                msg = bot.send_message(call.message.chat.id, "⏰ No hay alarmas configuradas para esta cita.\n\nEscribe cuándo quieres el aviso (ej: '30 minutos antes', '1 hora antes' o '26-06-2026 10:00'):")
            else:
                texto_alarmas = "⏰ *Alarmas actuales para esta cita:*\n\n"
                for a in alarmas:
                    texto_alarmas += f"• 🔔 {a[1]}\n"
                
                texto_alarmas += "\nEscribe cuándo quieres añadir otra alarma:"
                msg = bot.send_message(call.message.chat.id, texto_alarmas, parse_mode="Markdown")
            
            bot.register_next_step_handler(msg, process_add_alarma, cita_id)

    def process_add_nota(message, cita_id):
        if message.text.lower().strip() == 'cancelar':
            bot.reply_to(message, "Acción cancelada.")
            return
            
        database.add_nota(cita_id, message.text)
        
        markup = keyboards.get_cita_opciones_keyboard(cita_id)
        bot.reply_to(message, "✅ Nota guardada con éxito. ¿Quieres hacer algo más con esta cita?", reply_markup=markup)

    def process_add_alarma(message, cita_id):
        if message.text.lower().strip() == 'cancelar':
            bot.reply_to(message, "Acción cancelada.")
            return
            
        database.add_alarma(cita_id, message.text)
        
        markup = keyboards.get_cita_opciones_keyboard(cita_id)
        bot.reply_to(message, "✅ Alarma/Aviso guardado con éxito. ¿Quieres gestionar algo más de esta cita?", reply_markup=markup)

    # ------------------------------------------
    # INTERACCIÓN BÁSICA CON IA (Texto libre)
    # ------------------------------------------
    @bot.message_handler(func=lambda message: not message.text.startswith('/') and not message.reply_to_message)
    def chat_ia(message):
        user_id = message.from_user.id
        
        usos_hoy = database.get_uso_ia_hoy(user_id)
        if usos_hoy >= LIMITE_IA_DIARIO:
            bot.reply_to(message, "Has alcanzado tu límite diario de uso de IA.")
            return
            
        nuevo_total = database.incrementar_uso_ia(user_id)
        respuesta = utils.generar_respuesta_texto(message.text)
        
        if nuevo_total % 5 == 0: 
            bot.send_message(ADMIN_USER_ID, f"📊 El usuario {user_id} lleva {nuevo_total} usos de IA hoy.")
            
        bot.reply_to(message, respuesta)
