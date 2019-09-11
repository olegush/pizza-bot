import os

from dotenv import load_dotenv
import requests
from requests.exceptions import HTTPError, ConnectionError


from moltin_imports import (check_resp_json, get_headers, MoltinError, MOLTIN_API_URL,
                    MOLTIN_API_OAUTH_URL, MOLTIN_ERR_MSG, MOLTIN_API_FLOW_SLUG,
                    DVMN_ERR_MSG, DvmnError)


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
