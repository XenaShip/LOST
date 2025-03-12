import os
from venv import logger

import django
import asyncio
import random

from telegram import Bot
from telethon import TelegramClient, events
from dotenv import load_dotenv
from asgiref.sync import sync_to_async
import requests
# from __future__ import annotations
import time
from yandex_cloud_ml_sdk import YCloudML

# Загружаем переменные окружения
load_dotenv()

# Настроить Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from main.models import MESSAGE  # Используем новую модель

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
API_ID =  os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
SESSION_NAME = "session_name"
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
TELEGRAM_CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID")
YANDEX_GPT_API_KEY = os.getenv("YANDEX_GPT_API_KEY")

client = TelegramClient(SESSION_NAME, API_ID, API_HASH, system_version='1.2.3-zxc-custom', device_model='aboba-linux-custom', app_version='1.0.1')

def process_text_with_gpt(text):
    """Отправка текста в Yandex GPT и получение измененного текста"""
    sdk = YCloudML(
        folder_id="b1gk7ilr2af6cdodrhug",
        auth="AQVN0qY2FwtYfFSLdASCvKqwKp_gK76YlOEFpNqV",
    )

    model = sdk.models.completions("yandexgpt")

    # Variant 1: wait for the operation to complete using 5-second sleep periods

    print("Variant 1:")
    messages_1 = [
        {
            "role": "system",
            "text": "Переформулируй объявление под шаблон: кол-во комнат, цена, адрес, условия, описание, контакты. Если заданный текст- не объявление, ответь словом нет",
        },
        {
            "role": "user",
            "text": text,
        },
    ]

    operation = model.configure(temperature=0.3).run_deferred(messages_1)

    status = operation.get_status()
    while status.is_running:
        time.sleep(5)
        status = operation.get_status()

    result = operation.get_result()
    return result.text


@client.on(events.NewMessage(chats=CHANNEL_USERNAMES))
async def new_message_handler(event):
    if event.message:
        text = event.message.text or ""
        images = []

        # Получаем изображения, если есть
        if event.message.media:
            for attr in [event.message.photo, event.message.document]:
                if attr:
                    file_path = await client.download_media(attr)
                    images.append(file_path)


        # Сохраняем в Django-модель MESSAGE
        message = await sync_to_async(MESSAGE.objects.create)(
            text=text,
            images=images if images else None
        )
        # Обрабатываем текст с Yandex GPT
        new_text = await asyncio.to_thread(process_text_with_gpt, text)
        print(new_text)
        bot = Bot(token=BOT_TOKEN)
        if new_text:
            await bot.send_message(chat_id=TELEGRAM_CHANNEL_ID, text=new_text)
        delay = random.uniform(5, 25)
        await asyncio.sleep(delay)


async def main():
    await client.start()
    print("Бот слушает каналы...")
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())