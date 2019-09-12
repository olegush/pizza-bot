import os
from dotenv import load_dotenv

import requests
from requests.exceptions import HTTPError, ConnectionError


MOLTIN_API_URL = 'https://api.moltin.com/v2'
MOLTIN_API_OAUTH_URL = 'https://api.moltin.com/oauth/access_token'
MOLTIN_ERR_MSG = 'Moltin API returns error:'
MOLTIN_FLOW_ADDRESSES = 'addresses2'
MOLTIN_FLOW_CUSTOMERS = 'customers2'

load_dotenv()


class MoltinError(Exception):
    def __init__(self, message):
        self.message = message


def check_resp_json(resp):
    if 'errors' in resp.json():
        raise MoltinError(f'{MOLTIN_ERR_MSG} {resp.json()}')


def get_headers(func):
    def wrapper(*args):
        moltin_client_id = os.getenv('MOLTIN_CLIENT_ID')
        moltin_client_secret = os.getenv('MOLTIN_CLIENT_SECRET')
        data = {'client_id': str(moltin_client_id),
                'client_secret': str(moltin_client_secret),
                'grant_type': 'client_credentials'}
        try:
            resp = requests.post(MOLTIN_API_OAUTH_URL, data=data)
            resp.raise_for_status()
            check_resp_json(resp)
            moltin_token = resp.json()['access_token']
            headers = {
                'Authorization': 'Bearer {}'.format(moltin_token),
                'Content-Type': 'application/json'
            }
            return func(headers, *args)
        except HTTPError as e:
            raise MoltinError(f'{MOLTIN_ERR_MSG} {e}')
        except ConnectionError as e:
            raise MoltinError(f'{MOLTIN_ERR_MSG} {e}')
    return wrapper


@get_headers
def get_products(headers):
    resp = requests.get(f'{MOLTIN_API_URL}/products', headers=headers)
    resp.raise_for_status()
    check_resp_json(resp)
    products = resp.json()['data']
    return {product['id']: product['name'] for product in products}


@get_headers
def get_product(headers, product_id):
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


@get_headers
def get_cart(headers, cart_id):
    resp = requests.get(f'{MOLTIN_API_URL}/carts/{cart_id}/items',
                        headers=headers)
    resp.raise_for_status()
    check_resp_json(resp)
    cart = resp.json()
    products = '\n'.join((f"{product['name']}: {product['quantity']} шт. по {product['unit_price']['amount']} руб." for product in cart['data']))
    total = int(cart['meta']['display_price']['with_tax']['formatted'])
    return cart, products, total


@get_headers
def get_customer(headers, id):
    resp = requests.get(f'{MOLTIN_API_URL}/flows/{MOLTIN_FLOW_CUSTOMERS}/entries/{id}',
                        headers=headers)
    resp.raise_for_status()
    check_resp_json(resp)
    data = resp.json()['data']
    return data['latitude'], data['longitude'], data['nearest_shop_id']


@get_headers
def get_addresses(headers):
    resp = requests.get(f'{MOLTIN_API_URL}/flows/{MOLTIN_FLOW_ADDRESSES}/entries',
                        headers=headers)
    resp.raise_for_status()
    check_resp_json(resp)
    return resp.json()['data']


@get_headers
def get_address(headers, id):
    resp = requests.get(f'{MOLTIN_API_URL}/flows/{MOLTIN_FLOW_ADDRESSES}/entries/{id}',
                        headers=headers)
    resp.raise_for_status()
    check_resp_json(resp)
    data = resp.json()['data']
    return data['address'], data['courier_telegram_id']


@get_headers
def add_customer(headers, chat_id, latitude, longitude, address, nearest_shop_id):
    data = {
        'data': {
            'type': 'entry',
            'id_field': chat_id,
            'latitude': latitude,
            'longitude': longitude,
            'address': address,
            'nearest_shop_id': nearest_shop_id,
        }
    }
    resp = requests.post(f'{MOLTIN_API_URL}/flows/{MOLTIN_FLOW_CUSTOMERS}/entries',
                        headers=headers, json=data)
    resp.raise_for_status()
    check_resp_json(resp)
    return resp.json()['data']['id']


@get_headers
def add_to_cart(headers, cart_id, product_id):
    data = {
        'data': {
            'id': product_id,
            'type': 'cart_item',
            'quantity': 1,
        }
    }
    headers['X-MOLTIN-CURRENCY'] = 'RUB'
    resp = requests.post(f'{MOLTIN_API_URL}/carts/{cart_id}/items',
                        headers=headers, json=data)
    resp.raise_for_status()
    check_resp_json(resp)
    cart = resp.json()
    products = '\n'.join((f"{product['name']}: {product['quantity']} шт. по {product['unit_price']['amount']} руб." for product in cart['data']))
    total = int(cart['meta']['display_price']['with_tax']['formatted'])
    return cart, products, total


@get_headers
def delete_from_cart(headers, cart_id, item_id):
    resp = requests.delete(f'{MOLTIN_API_URL}/carts/{cart_id}/items/{item_id}',
                            headers=headers)
    resp.raise_for_status()
    check_resp_json(resp)
    return resp.json()











@get_headers
def create_flow(headers, name):
    data = {
        'data': {
            'type': 'flow',
            'name': name,
            'slug': name,
            'description': '',
            'enabled': True
        }
    }
    resp = requests.post(f'{MOLTIN_API_URL}/flows', headers=headers, json=data)
    resp.raise_for_status()
    check_resp_json(resp)
    return resp.json()


@get_headers
def create_fields(headers, flow_id, fields):
    result = ''
    for field, type in fields.items():
        data = {
            'data': {
                'type': 'field',
                'name': field,
                'slug': field,
                'field_type': type,
                'description': '',
                'required': False,
                'unique': False,
                'default': 0,
                'enabled': True,
                'order': 1,
                'relationships': {
                    'flow': {
                        'data': {
                            'type': 'flow',
                            'id': flow_id
                        }
                    }
                }
            }
        }
        resp = requests.post(f'{MOLTIN_API_URL}/fields', headers=headers, json=data)
        resp.raise_for_status()
        check_resp_json(resp)
        result +=  ', ' + str(resp.json()['data']['name'])
    return f'Fields: {result} was created'


@get_headers
def delete_flow(headers, id):
    resp = requests.delete(f'{MOLTIN_API_URL}/flows/{id}', headers=headers)
    resp.raise_for_status()
    return resp


@get_headers
def get_flow_fields(headers, name):
    resp = requests.get(f'{MOLTIN_API_URL}/flows/{name}/fields', headers=headers)
    resp.raise_for_status()
    return resp.json()
