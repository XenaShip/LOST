import os
import asyncio
import random
import logging
import time
from datetime import datetime

import django
import requests
from anyio import current_time
from telegram import Bot, InputMediaPhoto
from telethon import TelegramClient, events
from dotenv import load_dotenv
from asgiref.sync import sync_to_async
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from yandex_cloud_ml_sdk import YCloudML

# Загружаем переменные окружения
load_dotenv()

# Настроить Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from main.models import MESSAGE  # Используем новую модель

# Настройка логгера
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Конфигурация
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
API_ID = os.getenv("API_ID")
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
DOWNLOAD_FOLDER = "downloads/"

# Инициализация клиента Telethon
client = TelegramClient(SESSION_NAME, API_ID, API_HASH, system_version='1.2.3-zxc-custom', device_model='aboba-linux-custom', app_version='1.0.1')

def process_text_with_gpt(text):
    """Отправка текста в Yandex GPT и получение измененного текста"""
    sdk = YCloudML(
        folder_id=os.getenv("FOLDER_ID"),
        auth=os.getenv("AUTH"),
    )

    model = sdk.models.completions("yandexgpt")

    # Variant 1: wait for the operation to complete using 5-second sleep periods

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

async def download_image(image_url):
    """Скачивает изображение и сохраняет его локально."""
    response = requests.get(image_url, stream=True)
    if response.status_code == 200:
        filename = os.path.join("temp_images", os.path.basename(image_url))
        os.makedirs("temp_images", exist_ok=True)
        with open(filename, "wb") as file:
            for chunk in response.iter_content(1024):
                file.write(chunk)
        return filename
    return None


async def send_images_with_text(bot, chat_id, text, images):
    """Отправляет все изображения в Telegram, первое с текстом, остальные без."""
    media_group = []
    open_files = []  # Список открытых файлов, чтобы их не закрыл `with open`

    for index, image_path in enumerate(images):
        if os.path.exists(image_path):
            img_file = open(image_path, "rb")  # Открываем файл и сохраняем
            open_files.append(img_file)  # Добавляем в список, чтобы не закрылся

            if index == 0:
                media_group.append(InputMediaPhoto(media=img_file, caption=text))
            else:
                media_group.append(InputMediaPhoto(media=img_file))

    if media_group:
        await bot.send_media_group(chat_id=chat_id, media=media_group)

    # Закрываем файлы после отправки
    for img_file in open_files:
        img_file.close()


async def download_images(message):
    """Скачивает все фото из сообщения (включая альбом)"""
    images = []  # Список путей загруженных фото

    # 1️⃣ Проверяем, является ли сообщение частью альбома
    if message.grouped_id:
        # Получаем ВСЕ сообщения с таким же `grouped_id`
        album_messages = await client.get_messages(message.chat_id, min_id=message.id - 10, max_id=message.id + 10)
        photos = [msg.photo for msg in album_messages if msg.photo]  # Оставляем только фото
    else:
        # Если одиночное фото — обрабатываем только текущее сообщение
        photos = [message.photo] if message.photo else []

    # 2️⃣ Скачиваем фото
    for photo in photos:
        file_path = await client.download_media(photo, DOWNLOAD_FOLDER)
        if file_path:
            images.append(file_path)


@client.on(events.NewMessage(chats=CHANNEL_USERNAMES))
async def new_message_handler(event):
    if event.message:
        text = event.message.text or ""
        images = []

        # Скачиваем изображения, если есть
        if event.message.media:
            if hasattr(event.message.media, "photo"):
                current_message = event.message

                # Проверяем, есть ли у сообщения grouped_id (является ли оно частью альбома)
                if current_message.grouped_id:
                    # Получаем все сообщения с тем же grouped_id
                    album_messages = await client.get_messages(
                        event.message.chat_id,
                        ids=range(current_message.id - 10, current_message.id + 10)  # Захватываем небольшой диапазон
                    )

                    # Фильтруем только те сообщения, которые имеют тот же grouped_id и не являются None
                    album_messages = [
                        msg for msg in album_messages
                        if
                        msg is not None and hasattr(msg, 'grouped_id') and msg.grouped_id == current_message.grouped_id
                    ]

                    # Извлекаем все фото из альбома
                    photos = [msg.photo for msg in album_messages if msg.photo]
                else:
                    # Если это не альбом, просто берем фото из текущего сообщения
                    photos = [current_message.photo] if current_message.photo else []

                # 2️⃣ Скачиваем фото
                for photo in photos:
                    file_path = await client.download_media(photo, DOWNLOAD_FOLDER)
                    if file_path:
                        images.append(file_path)

        # Сохраняем в Django-модель MESSAGE
        message = await sync_to_async(MESSAGE.objects.create)(
            text=text,
            images=images if images else None
        )

        # Обрабатываем текст с Yandex GPT
        new_text = await asyncio.to_thread(process_text_with_gpt, text)
        logger.info(f"Обработанный текст: {new_text}")

        # Отправляем сообщение в Telegram
        bot = Bot(token=BOT_TOKEN)
        if new_text and (new_text != 'Нет' and new_text != 'Нет.'):
            if images:
                await send_images_with_text(bot, TELEGRAM_CHANNEL_ID, new_text, images)
            else:
                await bot.send_message(chat_id=TELEGRAM_CHANNEL_ID, text=new_text)

        # Задержка перед следующим сообщением
        await asyncio.sleep(5)

async def main():
    await client.start()
    logger.info("Бот слушает каналы...")
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())