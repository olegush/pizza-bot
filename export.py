import os
import requests
from requests.exceptions import HTTPError, ConnectionError

from dotenv import load_dotenv


MOLTIN_API_URL = 'https://api.moltin.com/v2'
MOLTIN_API_OAUTH_URL = 'https://api.moltin.com/oauth/access_token'
MOLTIN_ERR_MSG = 'Moltin API returns error:'
TELEGRAM_ERR_MSG = 'Telegram API returns error:'

class MoltinError(Exception):
    def __init__(self, message):
        self.message = message


def check_resp_json(resp):
    if 'errors' in resp.json():
        raise MoltinError(f'{MOLTIN_ERR_MSG} {resp.json()}')


def get_headers(moltin_client_id, moltin_client_secret):
    data = {'client_id': str(moltin_client_id),
            'client_secret': str(moltin_client_secret),
            'grant_type': 'client_credentials'}
    try:
        resp = requests.post(MOLTIN_API_OAUTH_URL, data=data)
        resp.raise_for_status()
        check_resp_json(resp)
        moltin_token = resp.json()['access_token']
        return {
            'Authorization': 'Bearer {}'.format(moltin_token),
            #'Content-Type': 'application/json'
            'Content-Type': 'multipart/form-data'
        }
    except HTTPError as e:
        raise MoltinError(f'{MOLTIN_ERR_MSG} {e}')
    except ConnectionError as e:
        raise MoltinError(f'{MOLTIN_ERR_MSG} {e}')


def create_product():
    global headers
    print(headers)
    data = {
        'data': {
            'type': 'product',
            'name': 'test3',
            'slug': 'test3',
            'sku': 'test64623',
            'manage_stock': False,
            'description': 'test2 test2 tes2t',
            'price': [{'amount': 700, 'currency': 'RUB', 'includes_tax': True}],
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


def create_file():
    global headers
    print(headers)
    with open('pizza2.png', 'rb') as f:
        file = f.read()

    files = {
        'file': open('tmp/pizza4.jpg', 'rb').read(), 
        'public': True}
    }
    #print(files)

    try:
        resp = requests.post(f'{MOLTIN_API_URL}/files', headers=headers, data=files)
        print(resp)
        resp.raise_for_status()
        check_resp_json(resp)
        return resp.json()
    except HTTPError as e:
        raise MoltinError(f'{MOLTIN_ERR_MSG} {e}')


load_dotenv()
telegram_token = os.environ.get('TELEGRAM_TOKEN')
moltin_client_id = os.environ.get('MOLTIN_CLIENT_ID')
moltin_client_secret = os.environ.get('MOLTIN_CLIENT_SECRET')
headers = get_headers(moltin_client_id, moltin_client_secret)
#print(create_product())
print(create_file())
