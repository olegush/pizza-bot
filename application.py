from dotenv import load_dotenv
import os
import logging
from queue import Queue  # in python 2 it should be "from Queue"
from threading import Thread

from flask import Flask, request
import telegram
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice
from telegram.ext import (Updater, Filters, Dispatcher, CommandHandler,
                        MessageHandler, CallbackQueryHandler,
                        PreCheckoutQueryHandler, ShippingQueryHandler)

from main import handle_users_reply, handle_answer_payment, handle_successful_payment, error_callback


load_dotenv()


TG_TOKEN = os.getenv('TG_TOKEN')
URL = os.getenv('URL')

app = Flask(__name__)
bot = telegram.Bot(token=TG_TOKEN)
update_queue = Queue()
dispatcher = Dispatcher(bot, update_queue)
# Start the thread
thread = Thread(target=dispatcher.start, name='dispatcher')
thread.start()
#dispatcher = Dispatcher(bot, None, workers=0)
dispatcher.add_handler(CallbackQueryHandler(handle_users_reply, pass_job_queue=True))
dispatcher.add_handler(MessageHandler(Filters.text, handle_users_reply, pass_job_queue=True))
dispatcher.add_handler(MessageHandler(Filters.location, handle_users_reply, pass_job_queue=True))
dispatcher.add_handler(CommandHandler('start', handle_users_reply, pass_job_queue=True))
dispatcher.add_handler(PreCheckoutQueryHandler(handle_answer_payment))
dispatcher.add_handler(MessageHandler(Filters.successful_payment, handle_successful_payment))
dispatcher.add_error_handler(error_callback)


@app.route(f'/{TG_TOKEN}', methods=['POST'])
def respond():
    # Creates the Telegram bot, Dispatcher instance, registers all handlers,
    # get data from Telegram reguest, create update queue and process update.
    try:

        update = telegram.update.Update.de_json(request.get_json(force=True), bot)
        #dispatcher.process_update(update)
        update_queue.put(update)
        return 'ok'
    except Exception as e:
        logging.critical(e)


@app.route('/set_webhook', methods=['GET', 'POST'])
def set_webhook():
    s = bot.setWebhook(f'{URL}/{TG_TOKEN}')
    if s:
        return "webhook setup ok"
    else:
        return "webhook setup failed"


@app.route('/<file_name>.json', methods=['GET'])
def display_menu_json(file_name):
    with open(f'{file_name}.json') as f:
        return f.read()


@app.route("/")
def hello():
    return 'hello!'
