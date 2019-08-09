from dotenv import load_dotenv
import os
import logging

import requests
from requests.exceptions import HTTPError, ConnectionError
import redis
from telegram.ext import Filters, Updater
from telegram.ext import (CallbackQueryHandler, CommandHandler, MessageHandler,
                        PreCheckoutQueryHandler, ShippingQueryHandler)
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice
import yandex_geocoder
from geopy import distance

from common import (check_resp_json, get_headers, MoltinError, MOLTIN_API_URL,
                    MOLTIN_API_OAUTH_URL, MOLTIN_ERR_MSG, MOLTIN_FLOW_ADDRESSES,
                    MOLTIN_FLOW_CUSTOMERS, DVMN_ERR_MSG, DvmnError)

load_dotenv()

TELEGRAM_ERR_MSG = 'Telegram API returns error:'
REMINDER_TIME = 60 * 60
PAYMENT_PAYLOAD = os.environ.get('PAYMENT_PAYLOAD')

database = None


def error_callback(bot, update, error):
    try:
        logging.error(str(update))
    except Exception as e:
        logging.critical(f'{TELEGRAM_ERR_MSG} {e}')


def get_database_connection():
    global database
    if database is None:
        db_pwd = os.environ.get('REDIS_PWD')
        db_host = os.environ.get('REDIS_HOST')
        db_port = os.environ.get('REDIS_PORT')
        database = redis.Redis(host=db_host, port=db_port, password=db_pwd)
    return database


@get_headers
def get_products(headers):
    try:
        resp = requests.get(f'{MOLTIN_API_URL}/products', headers=headers)
        resp.raise_for_status()
        check_resp_json(resp)
        products = resp.json()['data']
        return {product['id']: product['name'] for product in products}
    except HTTPError as e:
        raise MoltinError(f'{MOLTIN_ERR_MSG} {e}')


@get_headers
def get_product(headers, product_id):
    try:
        resp = requests.get(f'{MOLTIN_API_URL}/products/{product_id}',
                            headers=headers)
        resp.raise_for_status()
        check_resp_json(resp)
        product = resp.json()['data']
        name = product['name']
        description = product['description']
        price = product['price'][0]['amount']
        id_img = product['relationships']['main_image']['data']['id']
        resp_img = requests.get(f'{MOLTIN_API_URL}/files/{id_img}',
                                headers=headers)
        resp_img.raise_for_status()
        check_resp_json(resp_img)
        href_img = resp_img.json()['data']['link']['href']
        return name, description, price, href_img
    except HTTPError as e:
        raise MoltinError(f'{MOLTIN_ERR_MSG} {e}')


@get_headers
def get_cart(headers, cart_id):
    try:
        resp = requests.get(f'{MOLTIN_API_URL}/carts/{cart_id}/items',
                            headers=headers)
        resp.raise_for_status()
        check_resp_json(resp)
        cart = resp.json()
        products = '\n'.join((f"{product['name']}: {product['quantity']} шт. по {product['unit_price']['amount']} руб." for product in cart['data']))
        total = int(cart['meta']['display_price']['with_tax']['formatted'])
        return cart, products, total
    except HTTPError as e:
        raise MoltinError(f'{MOLTIN_ERR_MSG} {e}')


@get_headers
def get_customer(headers, id):
    try:
        resp = requests.get(f'{MOLTIN_API_URL}/flows/{MOLTIN_FLOW_CUSTOMERS}/entries/{id}',
                            headers=headers)
        resp.raise_for_status()
        check_resp_json(resp)
        data = resp.json()['data']
        return data['latitude'], data['longitude'], data['nearest']
    except HTTPError as e:
        raise MoltinError(f'{MOLTIN_ERR_MSG} {e}')


@get_headers
def get_address(headers, id):
    try:
        resp = requests.get(f'{MOLTIN_API_URL}/flows/{MOLTIN_FLOW_ADDRESSES}/entries/{id}',
                            headers=headers)
        resp.raise_for_status()
        check_resp_json(resp)
        data = resp.json()['data']
        return data['address'], data['courier_telegram_id']
    except HTTPError as e:
        raise MoltinError(f'{MOLTIN_ERR_MSG} {e}')


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


@get_headers
def add_customer(headers, chat_id, lat, long, address, nearest):
    try:
        data = {
            'data': {
                'type': 'entry',
                'id_field': chat_id,
                'latitude': lat,
                'longitude': long,
                'address': address,
                'nearest': nearest,
            }
        }
        resp = requests.post(f'{MOLTIN_API_URL}/flows/{MOLTIN_FLOW_CUSTOMERS}/entries',
                            headers=headers, json=data)
        resp.raise_for_status()
        check_resp_json(resp)
        return resp.json()['data']['id']
    except HTTPError as e:
        raise MoltinError(f'{MOLTIN_ERR_MSG} {e}')


@get_headers
def add_to_cart(headers, cart_id, product_id):
    data = {
        'data': {
            'id': product_id,
            'type': 'cart_item',
            'quantity': 1,
        }
    }
    try:
        headers['X-MOLTIN-CURRENCY'] = 'RUB'
        resp = requests.post(f'{MOLTIN_API_URL}/carts/{cart_id}/items',
                            headers=headers, json=data)
        resp.raise_for_status()
        check_resp_json(resp)
        cart = resp.json()
        products = '\n'.join((f"{product['name']}: {product['quantity']} шт. по {product['unit_price']['amount']} руб." for product in cart['data']))
        total = int(cart['meta']['display_price']['with_tax']['formatted'])
        return cart, products, total
    except HTTPError as e:
        raise MoltinError(f'{MOLTIN_ERR_MSG} {e}')


def add_reminder(bot, job):
    bot.send_message(text=f'*текст напоминания через REMINDER_TIME секунд*',
                    chat_id=job.context)


@get_headers
def delete_from_cart(headers, cart_id, item_id):
    try:
        resp = requests.delete(f'{MOLTIN_API_URL}/carts/{cart_id}/items/{item_id}',
                                headers=headers)
        resp.raise_for_status()
        check_resp_json(resp)
        return resp.json()
    except HTTPError as e:
        raise MoltinError(f'{MOLTIN_ERR_MSG} {e}')


@get_headers
def display_address(headers, bot, chat_id, lat, long, address_customer):
    if lat is None and long is None:
        text = 'Не могу определить координаты. Уточните пожалуйста адрес.'
        bot.send_message(text=text, chat_id=chat_id)
        return False
    try:
        resp = requests.get(f'{MOLTIN_API_URL}/flows/{MOLTIN_FLOW_ADDRESSES}/entries',
                            headers=headers)
        resp.raise_for_status()
        check_resp_json(resp)
        addresses = resp.json()['data']
    except HTTPError as e:
        raise MoltinError(f'{MOLTIN_ERR_MSG} {e}')
    for address in addresses:
        address['distance'] = distance.distance(
                                            (lat, long),
                                            (address['latitude'], address['longitude'])
                                        ).km
    nearest_address = min(addresses, key=lambda x: x['distance'])
    nearest_distance = round(nearest_address['distance'], 1)
    nearest_id = nearest_address['id']
    nearest_address = nearest_address['address']

    if nearest_distance > 20:
        text = f'Ближайшая пиццерия  аж в {nearest_distance} км от вас! Простите, но так далеко доставить не сможем :('
        bot.send_message(text=text, chat_id=chat_id)
        return False
    elif nearest_distance > 5:
        text = f'Ближайшая пиццерия в {nearest_distance} км от вас по адресу {nearest_address}. Заберете сами? Или доставим за 300 рублей'
    elif nearest_distance > 0.5:
        text = f'Ближайшая пиццерия в {nearest_distance} км от вас по адресу {nearest_address}. Заберете сами? Или привезем за самокате за 100 рублей'
    else:
        text = f'Вы совсем рядом! Ближайшая пиццерия всего в {nearest_distance} км от вас по адресу {nearest_address}. Заберете сами? Или можем доставить бесплатно.'
    id_customer = add_customer(chat_id, lat, long, address_customer, nearest_id)
    database.set(f'{chat_id}_id_customer', id_customer)
    keyboard = [[InlineKeyboardButton('ДОСТАВКА', callback_data='goto_checkout_delivery')]]
    keyboard.append([InlineKeyboardButton('САМОВЫВОЗ', callback_data='goto_checkout_pickup')])
    reply_markup = InlineKeyboardMarkup(keyboard)
    bot.send_message(text=text, parse_mode='Markdown', chat_id=chat_id, reply_markup=reply_markup)
    return True


def display_menu(bot, chat_id):
    products = get_products().items()
    keyboard = [[InlineKeyboardButton(product_name, callback_data=product_id)]
                for (product_id, product_name) in products]
    keyboard.append([InlineKeyboardButton('ВАША КОРЗИНА', callback_data='goto_cart')])
    reply_markup = InlineKeyboardMarkup(keyboard)
    bot.send_message(text='Приветствуем Вас в пицца-боте!\nВот наши пиццы:\n',
                    chat_id=chat_id, reply_markup=reply_markup)


def display_description(bot, query_data, chat_id):
    product_id = query_data
    name, description, price, href_img = get_product(query_data)
    text = f'"{name}"\n\n{description}\n\n{price} рублей'
    keyboard = [[InlineKeyboardButton('ЗАКАЗАТЬ', callback_data=f'{product_id}')]]
    keyboard.append([InlineKeyboardButton('МЕНЮ', callback_data='goto_menu')])
    keyboard.append([InlineKeyboardButton('ВАША КОРЗИНА', callback_data='goto_cart')])
    reply_markup = InlineKeyboardMarkup(keyboard)
    bot.send_photo(chat_id=chat_id, photo=href_img, caption=text,
                    reply_markup=reply_markup)


def display_cart(bot, cart, products, total, chat_id):
    keyboard = [[InlineKeyboardButton(f"Delete {product['name']}", callback_data=product['id'])] for product in cart['data']]
    keyboard.append([InlineKeyboardButton('МЕНЮ', callback_data='goto_menu')])
    if total > 0:
        keyboard.append([InlineKeyboardButton('ОФОРМИТЬ ЗАКАЗ', callback_data='goto_checkout_geo')])
    reply_markup = InlineKeyboardMarkup(keyboard)
    bot.send_message(text=f'ВАША КОРЗИНА:\n{products}\nСумма:{total} руб.',
                    chat_id=chat_id, reply_markup=reply_markup)


@get_headers
def display_address(headers, bot, chat_id, lat, long, address_customer):
    if lat is None and long is None:
        text = 'Не могу определить координаты. Уточните пожалуйста адрес.'
        bot.send_message(text=text, chat_id=chat_id)
        return False
    try:
        resp = requests.get(f'{MOLTIN_API_URL}/flows/{MOLTIN_FLOW_ADDRESSES}/entries', headers=headers)
        resp.raise_for_status()
        check_resp_json(resp)
        addresses = resp.json()['data']
    except HTTPError as e:
        raise MoltinError(f'{MOLTIN_ERR_MSG} {e}')
    for address in addresses:
        address['distance'] = distance.distance((lat, long), (address['latitude'], address['longitude'])).km
    nearest_address = min(addresses, key=lambda x: x['distance'])
    nearest_distance = round(nearest_address['distance'], 1)
    nearest_id = nearest_address['id']
    nearest_address = nearest_address['address']

    if nearest_distance > 20:
        text = f'Ближайшая пиццерия  аж в {nearest_distance} км от вас! Простите, но так далеко доставить не сможем :('
        bot.send_message(text=text, chat_id=chat_id)
        return False
    elif nearest_distance > 5:
        text = f'Ближайшая пиццерия в {nearest_distance} км от вас по адресу {nearest_address}. Заберете сами? Или доставим за 300 рублей'
    elif nearest_distance > 0.5:
        text = f'Ближайшая пиццерия в {nearest_distance} км от вас по адресу {nearest_address}. Заберете сами? Или привезем за самокате за 100 рублей'
    else:
        text = f'Вы совсем рядом! Ближайшая пиццерия всего в {nearest_distance} км от вас по адресу {nearest_address}. Заберете сами? Или можем доставить бесплатно.'
    id_customer = add_customer(chat_id, lat, long, address_customer, nearest_id)
    database.set(f'{chat_id}_id_customer', id_customer)
    keyboard = [[InlineKeyboardButton('ДОСТАВКА', callback_data='goto_checkout_delivery')]]
    keyboard.append([InlineKeyboardButton('САМОВЫВОЗ', callback_data='goto_checkout_pickup')])
    reply_markup = InlineKeyboardMarkup(keyboard)
    bot.send_message(text=text, parse_mode='Markdown', chat_id=chat_id, reply_markup=reply_markup)

    return True


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
    if display_address(bot, chat_id, lat, long, address_customer):
        return 'HANDLE_CHECKOUT_RECEIPT'
    else:
        return 'HANDLE_CHECKOUT_GEO'


def handle_checkout_receipt(bot, update, job_queue):
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
        job_queue.run_once(add_reminder, REMINDER_TIME, context=chat_id)
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
        provider_token = os.environ.get('PAYMENT_TOKEN_TRANZZO')
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
    except Exception as e:
        raise e


def main(telegram_token):
    # Creates the Telegram Updater, registers all handlers and
    # starts polling updates from Telegram.
    try:
        updater = Updater(telegram_token)
        dispatcher = updater.dispatcher
        dispatcher.add_handler(CallbackQueryHandler(handle_users_reply, pass_job_queue=True))
        dispatcher.add_handler(MessageHandler(Filters.text, handle_users_reply, pass_job_queue=True))
        dispatcher.add_handler(MessageHandler(Filters.location, handle_users_reply, pass_job_queue=True))
        dispatcher.add_handler(CommandHandler('start', handle_users_reply, pass_job_queue=True))
        dispatcher.add_handler(PreCheckoutQueryHandler(handle_answer_payment))
        dispatcher.add_handler(MessageHandler(Filters.successful_payment, handle_successful_payment))
        dispatcher.add_error_handler(error_callback)
        updater.start_polling(clean=True)
        updater.idle()
    except Exception as e:
        logging.critical(e)


if __name__ == '__main__':
    main(os.environ.get('TELEGRAM_TOKEN'))
