import os
import django
import asyncio
import random
from telethon import TelegramClient, events
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Настроить Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from main.models import MESSAGE  # Используем новую модель

# API-ключи из my.telegram.org
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
SESSION_NAME = "session_name"  # Название файла сессии
CHANNEL_USERNAME = "loltestneedxenaship"  # Юзернейм или ID канала

client = TelegramClient(SESSION_NAME, API_ID, API_HASH)


@client.on(events.NewMessage(chats=CHANNEL_USERNAME))
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
        delay = random.uniform(5, 25)  # Задержка от 5 до 25 секунд
        await asyncio.sleep(delay)

        # Сохраняем в Django-модель MESSAGE
        MESSAGE.objects.create(
            text=text,
            images=images if images else None  # Сохраняем только если есть изображения
        )
        print(f"Сохранено сообщение: {text[:50]}...")


client.start()
print("Бот слушает канал...")
client.run_until_disconnected()
