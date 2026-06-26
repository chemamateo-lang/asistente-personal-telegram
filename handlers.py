import os
import datetime
from telebot import TeleBot
from config import ADMIN_USER_ID, LIMITE_IA_DIARIO
import database
import utils
import keyboards

# ==========================================
# CONFIGURACIÓN INICIAL
# ==========================================

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
    # GESTIÓN DE LA LISTA DE LA COMPRA
    # ------------------------------------------
    @bot.message_handler(commands=['comprar'])
    def ver_lista_compra(message):
        user_id = message.from_user.id
        items = database.get_compras(user_id)
        
        if not items:
            bot.reply_to(message, "Tu lista de la compra está vacía. Añade artículos escribiendo: */anadir_compra manzana*", parse_mode="Markdown")
        else:
            markup = keyboards.get_compras_keyboard(items)
            bot.reply_to(message, "🛒 *Tu Lista de la Compra*:", reply_markup=markup, parse_mode="Markdown")

    @bot.message_handler(commands=['anadir_compra'])
    def agregar_a_compra(message):
        user_id = message.from_user.id
        # Extraemos el texto después del comando
        articulo = message.text.replace('/anadir_compra', '').strip()
        
        if not articulo:
            bot.reply_to(message, "Por favor, indica qué quieres añadir. Ejemplo: `/anadir_compra leche`")
            return
            
        database.add_compra(user_id, articulo)
        bot.reply_to(message, f"✅ Añadido a la compra: *{articulo}*", parse_mode="Markdown")

    # Manejador de los botones en línea de la compra
    @bot.callback_query_handler(func=lambda call: call.data.startswith('toggle_') or call.data.startswith('delete_'))
    def callback_compra(call):
        accion, item_id_str = call.data.split('_')
        item_id = int(item_id_str)
        
        if accion == 'toggle':
            database.toggle_compra(item_id)
        elif accion == 'delete':
            database.delete_compra(item_id)
            
        # Actualizamos el teclado
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
    # INTERACCIÓN BÁSICA CON IA (Texto)
    # ------------------------------------------
    @bot.message_handler(func=lambda message: not message.text.startswith('/') and not message.reply_to_message)
    def chat_ia(message):
        user_id = message.from_user.id
        
        # Control "chivato" de uso diario de IA
        usos_hoy = database.get_uso_ia_hoy(user_id)
        if usos_hoy >= LIMITE_IA_DIARIO:
            bot.reply_to(message, "Has alcanzado tu límite diario de uso de IA.")
            # Opcional: avisar al admin por privado
            # bot.send_message(ADMIN_USER_ID, f"⚠️ El usuario {user_id} ha alcanzado el límite de IA.")
            return
            
        # Incrementamos contador y obtenemos respuesta
        nuevo_total = database.incrementar_uso_ia(user_id)
        respuesta = utils.generar_respuesta_texto(message.text)
        
        # Opcional: avisar a admin si llega a cierto umbral o cada vez
        if nuevo_total % 5 == 0: 
            bot.send_message(ADMIN_USER_ID, f"📊 El usuario {user_id} lleva {nuevo_total} usos de IA hoy.")
            
        bot.reply_to(message, respuesta)

    # ------------------------------------------
    # GESTIÓN DE CITAS Y ALARMAS (Esqueleto inicial)
    # ------------------------------------------
    @bot.message_handler(commands=['agenda'])
    def ver_agenda(message):
        # Aquí más adelante mostraremos las citas principales del usuario
        bot.reply_to(message, "📅 Módulo de agenda en construcción modular. Pronto podrás ver aquí tus citas.")
