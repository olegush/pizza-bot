import os
import re
from collections import OrderedDict

import requests
from requests.exceptions import HTTPError, ConnectionError
from dotenv import load_dotenv
from PIL import Image

from moltin import (check_resp_json, get_headers, MoltinError, MOLTIN_API_URL,
                    MOLTIN_API_OAUTH_URL, MOLTIN_ERR_MSG, MOLTIN_API_FLOW_SLUG)


SLUG_TRANS_MAP = {
    'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e',
    'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
    'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
    'ф': 'f', 'х': 'h', 'ц': 'z', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch',
    'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'y', 'я': 'ya'}
FOOD_VALUE_MAP = {
    'fats': 'жиры',
    'proteins': 'белки',
    'carbohydrates': 'углеводы',
    'kiloCalories': 'калорийность',
    'weight': 'вес'}
IMAGES_DIR = 'images'
WIDTH_SMALL = 400


def get_slug(name):
    slug = re.sub('[^\w ]+', '', name).strip().lower()
    slug = re.sub('[ ]+', '-', slug)
    slug = '{}'.format(
    ''.join([SLUG_TRANS_MAP[a] if a in SLUG_TRANS_MAP else a for a in slug])
    )
    return slug


@get_headers
def create_file(headers, file):
    files = {
        'file': open(file, 'rb'),
        'public': True
    }
    try:
        resp = requests.post(f'{MOLTIN_API_URL}/files', headers=headers, files=files)
        resp.raise_for_status()
        check_resp_json(resp)
        return resp.json()
    except HTTPError as e:
        raise MoltinError(f'{MOLTIN_ERR_MSG} {e}')


@get_headers
def create_relationship(headers, product_id, img_id):
    data = {
        'data': {
            'type': 'main_image',
            'id': img_id
        }
    }
    try:
        resp = requests.post(f'{MOLTIN_API_URL}/products/{product_id}/relationships/main-image', headers=headers, json=data)
        resp.raise_for_status()
        check_resp_json(resp)
        return resp.json()
    except HTTPError as e:
        raise MoltinError(f'{MOLTIN_ERR_MSG} {e}')


@get_headers
def create_product(headers, name, slug, sku, description, price):
    data = {
        'data': {
            'type': 'product',
            'name': name,
            'slug': slug,
            'sku': sku,
            'manage_stock': False,
            'description': description,
            'price': [{'amount': price, 'currency': 'RUB', 'includes_tax': True}],
            'status': 'live',
            'commodity_type': 'physical'
        }
    }
    try:
        resp = requests.post(f'{MOLTIN_API_URL}/products', headers=headers, json=data)
        resp.raise_for_status()
        check_resp_json(resp)
        return resp.json()
    except HTTPError as e:
        raise MoltinError(f'{MOLTIN_ERR_MSG} {e}')


def resize_image(slug):
    img = Image.open(f'{IMAGES_DIR}/{slug}.jpg')
    width, height = img.size
    img_res = img.resize((WIDTH_SMALL, WIDTH_SMALL* round(height / width)))
    filename_new = f'{slug}_small.jpg'
    img_res.save(f'{IMAGES_DIR}/{filename_new}', 'JPEG')
    return filename_new


def import_menu(url):
    try:
        response = requests.get(url)
        menu = response.json()
    except (HTTPError, ConnectionError) as e:
        raise DvmnError(f'{DVMN_ERR_MSG} {e}')
    try:
        for pizza in menu[1:]:
            id = pizza['id']
            slug = get_slug(pizza['name'])
            sku = f'{slug}{id}'
            food_value = OrderedDict(pizza['food_value']).items()
            food_value = ', '.join(f'{FOOD_VALUE_MAP[key]}: {amount}' for key, amount in food_value)
            description = '{}\n\n{}'.format(pizza['description'], food_value)
            moltin_product = create_product(pizza['name'], slug, sku, description, pizza['price'])
            resp = requests.get(pizza['product_image']['url'])
            with open(f'{IMAGES_DIR}/{slug}.jpg', 'wb') as file:
                file.write(resp.content)
            filename_new = resize_image(slug)
            moltin_file = create_file(f'{IMAGES_DIR}/{filename_new}')
            moltin_relationship = create_relationship(moltin_product['data']['id'], moltin_file['data']['id'])
            print('"{}" pizza exported successfully.'.format(pizza['name']))
    except HTTPError as e:
        raise MoltinError(f'{MOLTIN_ERR_MSG} {e}')


if __name__ == '__main__':
    load_dotenv()
    moltin_client_id = os.environ.get('MOLTIN_CLIENT_ID')
    moltin_client_secret = os.environ.get('MOLTIN_CLIENT_SECRET')
    headers = get_headers(moltin_client_id, moltin_client_secret)
    import_menu(os.environ.get('URL_MENU'))
