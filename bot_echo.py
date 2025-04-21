import os
import asyncio
import random
import logging
import time
from datetime import datetime
from aiogram import Bot
import django
import requests
from anyio import current_time
from telegram import Bot, InputMediaPhoto
from telegram.error import RetryAfter
from telethon import TelegramClient, events
from dotenv import load_dotenv
from asgiref.sync import sync_to_async
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from yandex_cloud_ml_sdk import YCloudML

from bot_cian import message_handler
from district import get_district_by_coords, get_coords_by_address
from make_info import process_text_with_gpt_price, process_text_with_gpt_sq, process_text_with_gpt_adress, \
    process_text_with_gpt_rooms
from meters import get_coordinates, find_nearest_metro

# Загружаем переменные окружения
load_dotenv()

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

bot2 = Bot(token=os.getenv("TOKEN3"))
# Конфигурация
PHONE_NUMBER = os.getenv('PHONE_NUMBER')
TELEGRAM_PASSWORD = os.getenv('TELEGRAM_PASSWORD')
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
SESSION_NAME = "session_name"
TELEGRAM_CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID")
YANDEX_GPT_API_KEY = os.getenv("YANDEX_GPT_API_KEY")
DOWNLOAD_FOLDER = "downloads/"
CHANNEL_USERNAMES = [
    "loltestneedxenaship",
    "coliferent",
    "arendamsk_mo",
    "lvngrm_msk",
    "Sdat_Kvartiru0",
    "bestflats_msk",
    "nebabushkin_msk",
    "loltestneedxenaship",
]
client = TelegramClient(SESSION_NAME, API_ID, API_HASH, system_version='1.2.3-zxc-custom', device_model='aboba-linux-custom', app_version='1.0.1')

@client.on(events.NewMessage(chats=CHANNEL_USERNAMES))
async def new_message_handler(event):
    print('333')

async def main():
    await client.connect()
    if not await client.is_user_authorized():
        await client.send_code_request(PHONE_NUMBER)
        code = input('Enter the code you received: ')
        await client.sign_in(PHONE_NUMBER, code)
        # Если нужен пароль (включена 2FA)
        if await client.is_user_authorized() is False:
            await client.sign_in(password=TELEGRAM_PASSWORD)
    async with client:
        logger.info("Бот слушает каналы...")
        await client.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())