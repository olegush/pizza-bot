import os
import re
from collections import OrderedDict

import requests
from requests.exceptions import HTTPError, ConnectionError
from dotenv import load_dotenv

from moltin import (check_resp_json, get_headers, MoltinError, MOLTIN_API_URL,
                    MOLTIN_API_OAUTH_URL, MOLTIN_ERR_MSG, MOLTIN_FLOW_ADDRESSES,
                    create_flow, create_fields)


FLOW_ADDRESSES_FIELDS = {
    'id_field': 'string',
    'address': 'string',
    'alias': 'string',
    'latitude': 'float',
    'longitude': 'float',
    'courier_telegram_id': 'string'
}


@get_headers
def import_addresses(headers, url):
    try:
        response = requests.get(url)
        addresses = response.json()
    except (HTTPError, ConnectionError) as e:
        raise DvmnError(f'{DVMN_ERR_MSG} {e}')
    try:
        for address in addresses:
            data = {
                'data': {
                    'type': 'entry',
                    'id_field': address['id'],
                    'address': address['address']['full'],
                    'alias': address['alias'],
                    'latitude': address['coordinates']['lat'],
                    'longitude': address['coordinates']['lon'],
                }
            }
            resp = requests.post(f'{MOLTIN_API_URL}/flows/{MOLTIN_FLOW_ADDRESSES}/entries', headers=headers, json=data)
            resp.raise_for_status()
            check_resp_json(resp)
            moltin_enrty = resp.json()['data']
            print('Address "{}" exported successfully.'.format(moltin_enrty['alias']))
    except HTTPError as e:
        raise MoltinError(f'{MOLTIN_ERR_MSG} {e}')


if __name__ == '__main__':
    load_dotenv()
    moltin_client_id = os.environ.get('MOLTIN_CLIENT_ID')
    moltin_client_secret = os.environ.get('MOLTIN_CLIENT_SECRET')
    headers = get_headers(moltin_client_id, moltin_client_secret)

    # Create flow
    moltin_flow_create = create_flow(MOLTIN_FLOW_ADDRESSES)
    print('Flow "{}" created'.format(moltin_flow_create['data']['name']))

    # Create fields
    moltin_create_fields = create_fields(
                                os.environ.get('MOLTIN_FLOW_ADDRESSES_ID'),
                                FLOW_ADDRESSES_FIELDS
                            )
    print(moltin_create_fields)

    # Export addresses
    moltin_addresses = import_addresses(os.environ.get('URL_ADDRESSES'))
    print(moltin_addresses)
