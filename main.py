from dotenv import load_dotenv
import os
import logging

import redis
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice
from telegram.ext import (Updater, Filters, Dispatcher,
                        CommandHandler, MessageHandler, CallbackQueryHandler,
                        PreCheckoutQueryHandler, ShippingQueryHandler)
import yandex_geocoder

from moltin import (get_cart, get_customer, get_address,
                    display_menu, display_description, display_cart, display_address,
                    add_to_cart, delete_from_cart)


load_dotenv()

URL = os.getenv('URL')
TG_TOKEN = os.getenv('TG_TOKEN')


TELEGRAM_ERR_MSG = 'Telegram API returns error:'
REMINDER_TIME = 60 * 60
PAYMENT_PAYLOAD = os.getenv('PAYMENT_PAYLOAD')

database = None


def error_callback(bot, update, error):
    try:
        logging.error(str(update))
    except Exception as e:
        logging.critical(f'{TELEGRAM_ERR_MSG} {e}')


def get_database_connection():
    global database
    if database is None:
        db_pwd = os.getenv('REDIS_PWD')
        db_host = os.getenv('REDIS_HOST')
        db_port = os.getenv('REDIS_PORT')
        database = redis.Redis(host=db_host, port=db_port, password=db_pwd)
    return database


def get_query_data(update):
    if update.message:
        query = update.message
        query_data = query.location if query.location else query.text
        return query.message_id, query.chat_id, query_data
    elif update.callback_query:
        query = update.callback_query
        return query.message.message_id, query.message.chat_id, query.data
    else:
        return


def add_reminder(bot, job):
    bot.send_message(text=f'*текст напоминания через {REMINDER_TIME} секунд*',
                    chat_id=job.context)


def handle_start(bot, update, job_queue):
    message_id, chat_id, query_data = get_query_data(update)
    display_menu(bot, chat_id)
    if query_data != '/start':
        bot.delete_message(chat_id=chat_id, message_id=message_id)
    return 'HANDLE_MENU'


def handle_menu(bot, update, job_queue):
    message_id, chat_id, query_data = get_query_data(update)
    if query_data == 'goto_cart':
        cart, products, total = get_cart(chat_id)
        display_cart(bot, cart, products, total, chat_id)
        bot.delete_message(chat_id=chat_id, message_id=message_id)
        return 'HANDLE_CART'
    display_description(bot, query_data, chat_id)
    bot.delete_message(chat_id=chat_id, message_id=message_id)
    return 'HANDLE_DESCRIPTION'


def handle_description(bot, update, job_queue):
    message_id, chat_id, query_data = get_query_data(update)
    if query_data == 'goto_menu':
        display_menu(bot, chat_id)
        bot.delete_message(chat_id=chat_id, message_id=message_id)
        return 'HANDLE_MENU'
    elif query_data == 'goto_cart':
        cart, products, total = get_cart(chat_id)
        display_cart(bot, cart, products, total, chat_id)
        bot.delete_message(chat_id=chat_id, message_id=message_id)
        return 'HANDLE_CART'
    else:
        product_id = query_data
        cart, products, total = add_to_cart(chat_id, product_id)
        display_cart(bot, cart, products, total, chat_id)
        bot.delete_message(chat_id=chat_id, message_id=message_id)
        return 'HANDLE_CART'


def handle_cart(bot, update, job_queue):
    message_id, chat_id, query_data = get_query_data(update)
    if query_data == 'goto_menu':
        display_menu(bot, chat_id)
        bot.delete_message(chat_id=chat_id, message_id=message_id)
        return 'HANDLE_MENU'
    elif query_data == 'goto_checkout_geo':
        bot.send_message(text=f'ОФОРМЛЕНИЕ ЗАКАЗА:\nДля доставки вашей пиццы'
                                ' отправьте нам геолокацию или адрес текстом.',
                        chat_id=chat_id)
        bot.delete_message(chat_id=chat_id, message_id=message_id)
        return 'HANDLE_CHECKOUT_GEO'
    else:
        delete_from_cart(chat_id, query_data)
        cart, products, total = get_cart(chat_id)
        display_cart(bot, cart, products, total, chat_id)
        bot.delete_message(chat_id=chat_id, message_id=message_id)
        return 'HANDLE_CART'


def handle_checkout_geo(bot, update, job_queue):
    global database
    message_id, chat_id, query_data = get_query_data(update)
    try:
        if isinstance(query_data, str):
            long, lat = yandex_geocoder.Client.coordinates(query_data)
            address_customer = query_data
        else:
            lat, long = query_data.latitude, query_data.longitude
            # TODO: add getting address by coordinates
            address_customer = ''
    except Exception as e:
        lat, long, address_customer = None, None, None
    bot.delete_message(chat_id=chat_id, message_id=message_id - 1)
    if display_address(bot, chat_id, lat, long, address_customer, database):
        return 'HANDLE_CHECKOUT_RECEIPT'
    else:
        return 'HANDLE_CHECKOUT_GEO'


def handle_checkout_receipt(bot, update, job_queue):
    global database
    message_id, chat_id, query_data = get_query_data(update)
    cart, products, total = get_cart(chat_id)
    customer_id = database.get(f'{chat_id}_id_customer').decode('utf-8')
    lat, long, nearest_id = get_customer(customer_id)
    address, courier_telegram_id = get_address(nearest_id)
    keyboard = [[InlineKeyboardButton('ПО КАРТЕ', callback_data='goto_payment_card')],
                [InlineKeyboardButton('НАЛИЧНЫМИ', callback_data='goto_payment_cash')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    if query_data == 'goto_checkout_delivery':
        bot.send_location(latitude=lat, longitude=long, chat_id=courier_telegram_id)
        bot.send_message(text=f'Заказ:\n{products}\nСумма:{total} руб.',
                        chat_id=courier_telegram_id)
        #job_queue.run_once(add_reminder, REMINDER_TIME, context=chat_id)
        bot.send_message(text=f'Заказ принят и скоро будет доставлен! Как будете оплачивать?', chat_id=chat_id, reply_markup=reply_markup)
    elif query_data == 'goto_checkout_pickup':
        bot.send_message(text=f'Отлично! Ждем вас по адресу: {address}. Как будете оплачивать?', chat_id=chat_id, reply_markup=reply_markup)
    bot.delete_message(chat_id=chat_id, message_id=message_id)

    return 'HANDLE_CHECKOUT_PAYMENT'


def handle_checkout_payment(bot, update, job_queue):
    message_id, chat_id, query_data = get_query_data(update)
    cart, products, total = get_cart(chat_id)
    if query_data == 'goto_payment_cash':
        bot.send_message(text=f'Договорились! Напоминаем, что вы заказали:\n{products}\nСумма:{total} руб.', chat_id=chat_id)
    elif query_data == 'goto_payment_card':
        title = 'Оплата заказа'
        description = f'{products}\nСумма:{total} руб.'
        payload = PAYMENT_PAYLOAD
        provider_token = os.getenv('PAYMENT_TOKEN_TRANZZO')
        start_parameter = 'test-payment'
        currency = 'RUB'
        price = total
        prices = [LabeledPrice('Test', price * 100)]
        bot.sendInvoice(chat_id, title, description, payload, provider_token,
                        start_parameter, currency, prices)
    bot.delete_message(chat_id=chat_id, message_id=message_id)


def handle_answer_payment(bot, update):
    query = update.pre_checkout_query
    if query.invoice_payload != PAYMENT_PAYLOAD:
        bot.answer_pre_checkout_query(pre_checkout_query_id=query.id, ok=False,
                                      error_message='Что-то пошло не так...')
    else:
        bot.answer_pre_checkout_query(pre_checkout_query_id=query.id, ok=True)


def handle_successful_payment(bot, update):
    update.message.reply_text('Спасибо за заказ!')


def handle_users_reply(bot, update, job_queue):
    # Handles all user's actions. Gets current statement,
    # runs relevant function and set new statement.
    global database
    database = get_database_connection()
    message_id, chat_id, query_data = get_query_data(update)
    if query_data == '/start':
        user_state = 'HANDLE_START'
    else:
        user_state = database.get(chat_id).decode('utf-8')
    states_functions = {
            'HANDLE_START': handle_start,
            'HANDLE_MENU': handle_menu,
            'HANDLE_DESCRIPTION': handle_description,
            'HANDLE_CART': handle_cart,
            'HANDLE_CHECKOUT_GEO': handle_checkout_geo,
            'HANDLE_CHECKOUT_RECEIPT': handle_checkout_receipt,
            'HANDLE_CHECKOUT_PAYMENT': handle_checkout_payment,
        }
    state_handler = states_functions[user_state]
    try:
        next_state = state_handler(bot, update, job_queue)
        database.set(chat_id, next_state)
    except MoltinError as e:
        logging.critical(e)
