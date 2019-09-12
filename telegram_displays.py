from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from geopy import distance

from moltin import get_products, get_product, add_customer


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
    keyboard = [[InlineKeyboardButton(f"УДАЛИТЬ {product['name']}", callback_data=product['id'])] for product in cart['data']]
    keyboard.append([InlineKeyboardButton('МЕНЮ', callback_data='goto_menu')])
    if total > 0:
        keyboard.append([InlineKeyboardButton('ОФОРМИТЬ ЗАКАЗ', callback_data='goto_checkout_geo')])
    reply_markup = InlineKeyboardMarkup(keyboard)
    bot.send_message(text=f'ВАША КОРЗИНА:\n{products}\nСумма:{total} руб.',
                    chat_id=chat_id, reply_markup=reply_markup)


def display_address(bot, chat_id, latitude, longitude, address_customer, addresses, database):
    if latitude is None and longitude is None:
        text = 'Не могу определить координаты. Уточните пожалуйста адрес.'
        bot.send_message(text=text, chat_id=chat_id)
        return False
    for address in addresses:
        address['distance'] = distance.distance(
                                            (latitude, longitude),
                                            (address['latitude'], address['longitude'])
                                        ).km
    nearest_address = min(addresses, key=lambda x: x['distance'])
    nearest_distance = round(nearest_address['distance'], 1)
    nearest_shop_id = nearest_address['id']
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
    id_customer = add_customer(chat_id, latitude, longitude, address_customer, nearest_shop_id)
    database.set(f'{chat_id}_id_customer', id_customer)
    keyboard = [[InlineKeyboardButton('ДОСТАВКА', callback_data='goto_checkout_delivery')]]
    keyboard.append([InlineKeyboardButton('САМОВЫВОЗ', callback_data='goto_checkout_pickup')])
    reply_markup = InlineKeyboardMarkup(keyboard)
    bot.send_message(text=text, parse_mode='Markdown', chat_id=chat_id, reply_markup=reply_markup)
    return True
