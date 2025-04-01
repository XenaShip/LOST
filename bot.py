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

# Настроить Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from main.models import MESSAGE, INFO, Subscription  # Используем новую модель

# Настройка логгера
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

bot2 = Bot(token=os.getenv("TOKEN3"))
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
            "text": "Переформулируй объявление под шаблон, отделив каждый пункт несколькими пустыми строчками: кол-во комнат, цена, адрес, условия, описание, контакты. Если заданный текст- не объявление, ответь словом нет. Добавь эмодзи в каждый пункт, если это объявление",
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


async def check_subscriptions_and_notify(info_instance):
    # Получаем все активные подписки
    subscriptions = await sync_to_async(list)(Subscription.objects.filter(is_active=True))

    # Получаем данные объявления
    ad_data = {
        'price': info_instance.price,
        'rooms': info_instance.rooms,
        'location': info_instance.location,
        'count_meters_metro': info_instance.count_meters_metro,
        'address': info_instance.adress,  # Обратите внимание: исправлено с adress на address
        'images': info_instance.message.images,  # Доступ к message через info_instance
        'description': info_instance.message.new_text
    }

    for subscription in subscriptions:
        if await sync_to_async(is_ad_match_subscription)(ad_data, subscription):
            await send_notification(subscription.user_id, ad_data, info_instance.message)


async def send_notification(user_id: int, ad_data: dict, message):
    """
    Отправляет уведомление о новом объявлении пользователю
    """
    try:
        message_text = message.new_text
        images = ad_data.get('images') or []  # Защита от None

        if images and isinstance(images, list):  # Явная проверка
            media_group = []

            # Первое изображение с подписью
            first_img = images[0]
            if first_img.startswith(("http://", "https://")):
                # Если это URL
                media_group.append(
                    InputMediaPhoto(media=first_img, caption=message_text, parse_mode="Markdown")
                )
            else:
                # Если это локальный путь
                with open(first_img, "rb") as img_file:
                    media_group.append(
                        InputMediaPhoto(media=img_file, caption=message_text, parse_mode="Markdown")
                    )

            # Остальные изображения
            for img_url in images[1:10]:
                if img_url.startswith(("http://", "https://")):
                    media_group.append(InputMediaPhoto(media=img_url))
                else:
                    with open(img_url, "rb") as img_file:
                        media_group.append(InputMediaPhoto(media=img_file))

            await bot2.send_media_group(chat_id=user_id, media=media_group)
        else:
            await bot2.send_message(
                chat_id=user_id,
                text=message_text,
                parse_mode="Markdown"
            )

    except RetryAfter as e:
        await asyncio.sleep(e.timeout)
        await send_notification(user_id, ad_data, message)
    except Exception as e:
        print(f"Ошибка при отправке уведомления: {e}")

def is_ad_match_subscription(ad_data, subscription):
    """Синхронная функция проверки соответствия подписки"""
    # Проверка цены
    if subscription.min_price is not None and ad_data['price'] < subscription.min_price:
        return False
    if subscription.max_price is not None and ad_data['price'] > subscription.max_price:
        return False

    # Проверка количества комнат
    if subscription.min_rooms is not None and ad_data['rooms'] < subscription.min_rooms:
        return False
    if subscription.max_rooms is not None and ad_data['rooms'] > subscription.max_rooms:
        return False

    # Проверка района
    if subscription.district != 'ANY' and ad_data['location'] != subscription.district:
        return False

    # Проверка расстояния до метро (если есть в данных)
    if ('count_meters_metro' in ad_data and
        subscription.max_metro_distance is not None and
        ad_data['count_meters_metro'] > subscription.max_metro_distance):
        return False

    return True


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

        # Обрабатываем текст с Yandex GPT
        new_text = await asyncio.to_thread(process_text_with_gpt, text)
        new_text = new_text.replace("*", "")
        logger.info(f"Обработанный текст: {new_text}")
        message = await sync_to_async(MESSAGE.objects.create)(
            text=text,
            images=images if images else None,
            new_text=new_text
        )
        if new_text != 'Нет' and new_text != 'Нет.':
            address=process_text_with_gpt_adress(new_text)
            coords=get_coords_by_address(address)
            info = await sync_to_async(INFO.objects.create)(
                message=message,
                price=process_text_with_gpt_price(new_text),
                count_meters_flat=process_text_with_gpt_sq(new_text),
                count_meters_metro=find_nearest_metro(*coords),
                location=get_district_by_coords(*coords),
                adress=process_text_with_gpt_adress(new_text),
                rooms=process_text_with_gpt_rooms(new_text)
            )
            asyncio.create_task(check_subscriptions_and_notify(info))
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