## Pizza Bot

This telegram bot is simple e-shop based on [Moltin API](https://moltin.com) and uses [state machine](https://en.wikipedia.org/wiki/Finite-state_machine) principles. Moltin CSM stores products, user cart and info. [Redis](https://redislabs.com/) DB stores current user statement.


## How to install and deploy

1. Get domain and SSL-certificate, put url to **.env** file.

```bash
URL=https://example.com
```

2. Python 3 and libraries from **requirements.txt** should be installed. Use virtual environment tool, for example **venv**

```bash
python3 -m venv venv_folder_name
source venv_folder_name/bin/activate
python3 -m pip install -r requirements.txt
```

3. Use WSGI - server, for example [Gunicorn](https://gunicorn.org). Create service:

```bash
$ sudo nano /etc/systemd/system/app.service

[Unit]
Description=gunicorn daemon
Requires=app.socket
After=network.target

[Service]
User=root
Group=www-data
WorkingDirectory=path_to_project
Environment="PATH=path_to_virtual_env_bin"
ExecStart=path_to_gunicorn \
          --access-logfile - \
          --workers 3 \
          --timeout 3000 \
          --bind unix:/run/app.sock \
          wsgi:app

[Install]
WantedBy=multi-user.target

```

4. Add Nginx config file:

```bash
$ sudo nano /etc/nginx/sites-available/project_name
server {
    server_name    example.com;
    location / {
        include proxy_params;
        proxy_pass http://unix:/run/app.sock;
    }
}
```

5. Create [Moltin account](https://dashboard.moltin.com) and get Moltin Client ID and Client secret. Put these parameters to **.env** file. Add your currency https://dashboard.moltin.com/app/settings/currencies

```bash
MOLTIN_CLIENT_ID=moltin_client_id
MOLTIN_CLIENT_SECRET=moltin_client_secret
```


6. For menu export you should have json file like this:
```javascript
[{
	"id": id,
	"name": name,
	"description": description,
	"food_value": {
		"fats": fats,
		"proteins": proteins,
		"carbohydrates": carbohydrates,
		"kiloCalories": kiloCalories,
		"weight": weight
	},
	"culture_name": "ru-RU",
	"product_image": {
		"url": img_url,
		"height": img_height,
		"width": img_width
	},
	"price": price
},
]
```

save this file on the URL_MENU and add **.env** with the parameter
```bash
URL_MENU=url_with_menu_json
```
Set the width of small image with WIDTH_SMALL constant and run **export_menu.py**. Then the process is finished, check your products [here](https://dashboard.moltin.com/app/catalogue/products). Also you'll got original and resized images in the IMAGES_DIR folder.


7. For addresses export you should have json file like this:
```javascript
[{
	"id": id,
	"alias": address_alias,
	"address": {
		"full": full_address,
		"city": city,
		"street": street,
		"street_type": street_type,
		"building": building
	},
	"coordinates": {
		"lat": latitude,
		"lon": longitude
	}
},
]
```

save this file on the URL_ADDRESSES and add it in the **.env**
```bash
URL_ADDRESSES=url_with_addresses_json
```

Set MOLTIN_FLOW_ADDRESSES constant in the **common.py**. This is the name of your flow with addresses. Then set FLOW_FIELDS constant in the **export_addresses.py**, MOLTIN_FLOW_ADDRESSES_ID ennviroment variable in the **.env**, run the file **export_addresses.py** and check FLOWS section on [your dashboard](https://dashboard.moltin.com/)


8. To create customers flow set MOLTIN_FLOW_CUSTOMERS constant in the **common.py**. This is the name of your flow with customers. Then set FLOW_FIELDS constant in the **create_customers.py**, MOLTIN_FLOW_CUSTOMERS_ID ennviroment variable in the **.env**, run the file **create_customers.py** and check FLOWS section on [your dashboard](https://dashboard.moltin.com/). Aslo, **common.py** contains more useful functions for work with Moltin API and you can use them.


9. Create new Telegram bot, get token and your ID.

10. Create Redis account, get host, port and password.

11. Update **.env** file.

```bash
TG=telegram_token
TELEGRAM_CHAT_ID_ADMIN=telegram_chat_id_admin
REDIS_HOST=redis_host
REDIS_PORT=redis_port
REDIS_PWD=redis_pwd
PAYMENT_PAYLOAD=your_secret_payment_payload
PAYMENT_TOKEN_TRANZZO=payment_token
```


## Quickstart

Run **main.py** and test your e-shop in Telegram.

![pizza-shop screenshot](screenshots/pizza-shop.png)



## Project Goals

The code is written for educational purposes on online-course for
web-developers [dvmn.org](https://dvmn.org/).
