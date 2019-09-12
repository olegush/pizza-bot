import os
import re
from collections import OrderedDict

import requests
from requests.exceptions import HTTPError, ConnectionError
from dotenv import load_dotenv

from moltin import (check_resp_json, get_headers, MoltinError, MOLTIN_API_URL,
                    MOLTIN_API_OAUTH_URL, MOLTIN_ERR_MSG, MOLTIN_FLOW_ADDRESSES,
                    create_flow, create_fields)


FLOW_CUSTOMERS_FIELDS = {
    'id_field': 'string',
    'latitude': 'float',
    'longitude': 'float',
    'address': 'string',
    'nearest_shop_id': 'string'
}


if __name__ == '__main__':
    load_dotenv()
    moltin_client_id = os.environ.get('MOLTIN_CLIENT_ID')
    moltin_client_secret = os.environ.get('MOLTIN_CLIENT_SECRET')
    headers = get_headers(moltin_client_id, moltin_client_secret)

    # Create flow
    moltin_flow_create = create_flow(MOLTIN_FLOW_CUSTOMERS)
    print('Flow "{}" created'.format(moltin_flow_create['data']['name']))

    # Create fields
    moltin_create_fields = create_fields(
                                os.environ.get('MOLTIN_FLOW_CUSTOMERS_ID'),
                                FLOW_CUSTOMERS_FIELDS
                            )
    print(moltin_create_fields)
