import os

from dotenv import load_dotenv
import requests
from requests.exceptions import HTTPError, ConnectionError


MOLTIN_API_URL = 'https://api.moltin.com/v2'
MOLTIN_API_OAUTH_URL = 'https://api.moltin.com/oauth/access_token'
MOLTIN_ERR_MSG = 'Moltin API returns error:'
MOLTIN_FLOW_ADDRESSES = 'addresses2'
MOLTIN_FLOW_CUSTOMERS = 'customers2'
DVMN_ERR_MSG = 'DVMN API returns error:'

load_dotenv()

class MoltinError(Exception):
    def __init__(self, message):
        self.message = message

class DvmnError(Exception):
    def __init__(self, message):
        self.message = message


def check_resp_json(resp):
    if 'errors' in resp.json():
        raise MoltinError(f'{MOLTIN_ERR_MSG} {resp.json()}')


def get_headers(func):
    def wrapper(*args):
        moltin_client_id = os.environ.get('MOLTIN_CLIENT_ID')
        moltin_client_secret = os.environ.get('MOLTIN_CLIENT_SECRET')
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
    try:
        resp = requests.post(f'{MOLTIN_API_URL}/flows', headers=headers, json=data)
        resp.raise_for_status()
        check_resp_json(resp)
        return resp.json()
    except HTTPError as e:
        raise MoltinError(f'{MOLTIN_ERR_MSG} {e}')


@get_headers
def create_fields(headers, flow_id, fields):
    try:
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
    except HTTPError as e:
        raise MoltinError(f'{MOLTIN_ERR_MSG} {e}')


@get_headers
def delete_flow(headers, id):
    try:
        resp = requests.delete(f'{MOLTIN_API_URL}/flows/{id}', headers=headers)
        resp.raise_for_status()
        return resp
    except HTTPError as e:
        raise MoltinError(f'{MOLTIN_ERR_MSG} {e}')


@get_headers
def get_flow_fields(headers, name):
    try:
        resp = requests.get(f'{MOLTIN_API_URL}/flows/{name}/fields', headers=headers)
        resp.raise_for_status()
        return resp.json()
    except HTTPError as e:
        raise MoltinError(f'{MOLTIN_ERR_MSG} {e}')
