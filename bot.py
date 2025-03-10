import os
import django
import asyncio
import random
from telethon import TelegramClient, events
from dotenv import load_dotenv
from asgiref.sync import sync_to_async
import requests

# Загружаем переменные окружения
load_dotenv()

# Настроить Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from main.models import MESSAGE  # Используем новую модель

# API-ключи из my.telegram.org
API_ID = int(os.getenv("API_ID"))
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
TELEGRAM_CHANNEL = os.getenv("TELEGRAM_CHANNEL")  # Куда отправлять
YANDEX_GPT_API_KEY = os.getenv("YANDEX_GPT_API_KEY")

client = TelegramClient(SESSION_NAME, API_ID, API_HASH, system_version='1.2.3-zxc-custom', device_model='aboba-linux-custom', app_version='1.0.1')

def process_text_with_gpt(text):
    """Отправка текста в Yandex GPT и получение измененного текста"""
    url = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
    headers = {
        "Authorization": f"Api-Key {YANDEX_GPT_API_KEY}",
        "Content-Type": "application/json",
    }
    data = {
        "model": "yandexgpt",
        "prompt": f"Перефразируй объявление в формате: Кол-во комнат, Адрес, Условия.\n\n{text}",
        "temperature": 0.7,
        "max_tokens": 200,
    }
    response = requests.post(url, json=data, headers=headers)
    if response.status_code == 200:
        return response.json().get("result", "")
    return ""

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

        # Имитация задержки (анти-спам)
        delay = random.uniform(5, 25)
        await asyncio.sleep(delay)

        # Сохраняем в Django-модель MESSAGE
        message = await sync_to_async(MESSAGE.objects.create)(
            text=text,
            images=images if images else None
        )

        # Обрабатываем текст с Yandex GPT
        new_text = await asyncio.to_thread(process_text_with_gpt, text)
        if new_text:
            await client.send_message(TELEGRAM_CHANNEL, new_text)

async def main():
    await client.start()
    print("Бот слушает каналы...")
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())