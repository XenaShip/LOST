import os
import asyncio
import random
import logging
import re
import time
from datetime import datetime
from telegram import InputMediaVideo
import telethon
from aiogram import Bot
import django
import requests
from anyio import current_time
from django.utils.regex_helper import contains
from telegram import Bot, InputMediaPhoto
from telegram.error import RetryAfter
from telethon import TelegramClient, events
from dotenv import load_dotenv
from asgiref.sync import sync_to_async
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from yandex_cloud_ml_sdk import YCloudML
import sys
import os

from bot_cian import message_handler
from district import get_district_by_coords, get_coords_by_address
from make_info import process_text_with_gpt_price, process_text_with_gpt_sq, process_text_with_gpt_adress, \
    process_text_with_gpt_rooms
from meters import get_coordinates, find_nearest_metro
from proccess import process_text_with_gpt2, process_text_with_gpt3, process_text_with_gpt

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
PHONE_NUMBER = os.getenv('PHONE_NUMBER')
TELEGRAM_PASSWORD = os.getenv('TELEGRAM_PASSWORD')
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
SESSION_NAME = "session_name_lost"

TELEGRAM_CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID")
YANDEX_GPT_API_KEY = os.getenv("YANDEX_GPT_API_KEY")
DOWNLOAD_FOLDER = "downloads/"

# Инициализация клиента Telethon
client = TelegramClient(SESSION_NAME, API_ID, API_HASH, system_version='1.2.3-zxc-custom',
                        device_model='aboba-linux-custom', app_version='1.0.1')


async def get_username_by_id(user_id):
    try:
        # Преобразуем ID в целое число
        user_id = int(user_id)
        # Получаем информацию о пользователе
        user = await client.get_entity(user_id)
        if user.username:
            return f"https://t.me/{user.username}"
    except Exception as e:
        logger.error(f"Ошибка получения username: {e}")
    return None  # Если не удалось получить username


async def process_contacts(text):
    # Получаем контакт через GPT
    raw_contact = await asyncio.to_thread(process_text_with_gpt2, text)
    print('process')

    # Если это tg:// ссылка - преобразуем
    if raw_contact.startswith("tg://user?id="):
        user_id = raw_contact.split("=")[1]
        return await get_username_by_id(user_id) or raw_contact

    return raw_contact


async def download_media(message):
    """
    Скачивает все медиа (фото и видео) из сообщения и альбомов (по grouped_id).
    Возвращает список словарей {'type': 'photo'/'video', 'path': путь_к_файлу'}.
    """
    media_list = []
    # Если сообщение – часть альбома, собираем все сообщения с этим grouped_id
    if message.grouped_id:
        album_msgs = await client.get_messages(
            message.chat_id,
            min_id=message.id - 20,
            max_id=message.id + 20
        )
        # Фильтруем сообщения того же альбома
        album_msgs = [m for m in album_msgs if m and m.grouped_id == message.grouped_id]
    else:
        album_msgs = [message]

    # Проходим по каждому сообщению альбома
    for msg in album_msgs:
        # Скачиваем фото или видео
        if msg.photo:
            file_path = await client.download_media(msg.photo, DOWNLOAD_FOLDER)
            if file_path:
                media_list.append({'type': 'photo', 'path': file_path})
        elif msg.video:
            file_path = await client.download_media(msg.video, DOWNLOAD_FOLDER)
            if file_path:
                media_list.append({'type': 'video', 'path': file_path})
    # Ограничиваем размер до 10 элементов
    return media_list[:10]


async def send_media_group(bot, chat_id, text, media_items):
    """
    Отправляет список медиа (фото и видео) в одном media_group.
    Подпись (text) добавляется только к первому элементу.
    """
    if not media_items:
        # Если медиа нет, отправляем просто текст
        await bot.send_message(chat_id, text)
        return

    media_group = []
    open_files = []
    for idx, item in enumerate(media_items):
        file_path = item['path']
        if not os.path.exists(file_path):
            continue
        f = open(file_path, 'rb')
        open_files.append(f)
        # Первый элемент получает подпись
        caption = text if idx == 0 else None
        if item['type'] == 'photo':
            media = InputMediaPhoto(media=f, caption=caption)
        else:
            media = InputMediaVideo(media=f, caption=caption)
        media_group.append(media)

    # Отправляем одним media_group. Требуется 2–10 элементов:contentReference[oaicite:3]{index=3}.
    if len(media_group) == 1:
        # Если только один элемент, отправляем его обычным методом
        m = media_group[0]
        if isinstance(m, InputMediaPhoto):
            await bot.send_photo(chat_id, m.media, caption=text)
        else:
            await bot.send_video(chat_id, m.media, caption=text)
    else:
        await bot.send_media_group(chat_id=chat_id, media=media_group)
    # Закрываем файлы
    for f in open_files:
        f.close()


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
    logger.info(f"🔔 Начало обработки подписок для объявления {info_instance.id}")
    # Получаем все активные подписки
    subscriptions = await sync_to_async(list)(Subscription.objects.filter(is_active=True))
    logger.info(f"📋 Найдено {len(subscriptions)} активных подписок")
    if not subscriptions:
        logger.info("❌ Нет активных подписок, пропускаем уведомления")
        return
    # Получаем данные объявления
    ad_data = {
        'price': info_instance.price,
        'rooms': info_instance.rooms,
        'count_meters_flat': info_instance.count_meters_flat,  # Добавлено поле площади
        'location': info_instance.location,
        'count_meters_metro': info_instance.count_meters_metro,
        'address': info_instance.adress,
        'images': info_instance.message.images,
        'description': info_instance.message.new_text
    }
    for subscription in subscriptions:
        logger.info(f"🔍 Проверка подписки {subscription.id} (пользователь: {subscription.user_id})")
        is_match = await sync_to_async(is_ad_match_subscription)(ad_data, subscription)
        if is_match:
            logger.info(f"✅ Объявление подходит для подписки {subscription.id}")
            await send_notification(subscription.user_id, ad_data, info_instance.message)
        else:
            logger.info(f"❌ Объявление НЕ подходит для подписки {subscription.id}")


def escape_markdown(text: str) -> str:
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    return re.sub(f'([{re.escape(escape_chars)}])', r'\\\1', text)

def safe_parse_number(value):
    if value is None:
        return None
    if isinstance(value, str):
        value = value.replace(',', '.').strip()
        # оставляем только цифры и точку
        value = ''.join(c for c in value if c.isdigit() or c == '.')
    try:
        return float(value)
    except:
        return None


async def send_notification(user_id: int, ad_data: dict, message):
    """
    Отправка уведомления пользователю с поддержкой URL изображений (aiogram v3)

    """
    try:
        safe_text = message.new_text

        # Добавляем контакты, если их нет
        if "Контакты" not in safe_text:
            contacts = await asyncio.to_thread(process_text_with_gpt2, message.text)
            if contacts and contacts.lower() not in ['нет', 'нет.']:
                safe_text += " Контакты: " + contacts

        media_paths = ad_data.get('images') or []
        media_group = []

        for idx, media_path in enumerate(media_paths[:10]):
            caption = safe_text if idx == 0 else None

            # Aiogram v3 требует именованные аргументы
            if str(media_path).startswith("http"):
                media_group.append(InputMediaPhoto(media=media_path, caption=caption))
            elif os.path.exists(media_path):
                # локальный файл открывать не нужно, aiogram сам откроет по пути
                media_group.append(InputMediaPhoto(media=open(media_path, "rb"), caption=caption))
        await asyncio.sleep(5)
        if media_group:
            if len(media_group) == 1:
                await bot2.send_photo(chat_id=user_id, photo=media_group[0].media, caption=safe_text)
            else:
                await bot2.send_media_group(chat_id=user_id, media=media_group)
        else:
            await bot2.send_message(chat_id=user_id, text=safe_text)

        logger.info(f"[NOTIFY] Отправлено объявление пользователю {user_id}")

    except RetryAfter as e:
        logger.warning(f"[NOTIFY] Flood control, повтор через {e.timeout} сек.")
        await asyncio.sleep(e.timeout)
        await send_notification(user_id, ad_data, message)
    except Exception as e:
        logger.error(f"[NOTIFY] Ошибка при отправке уведомления пользователю {user_id}: {e}", exc_info=True)


def is_ad_match_subscription(ad_data, subscription):
    """
    Проверяет, подходит ли объявление под параметры подписки.
    Учитывает:
      - 0 комнат = студия (приравнивается к 1 комнате)
      - 0 м² = нераспознанная площадь (не используется для фильтрации)
      - если параметр подписки не задан (None или 'ANY'), он пропускается
    """
    try:
        ad_price = safe_parse_number(ad_data.get('price'))
        ad_rooms = safe_parse_number(ad_data.get('rooms'))
        ad_flat_area = safe_parse_number(ad_data.get('count_meters_flat'))
        ad_metro_distance = safe_parse_number(ad_data.get('count_meters_metro'))

        # Студии (0 комнат) считаем как 1 комнату
        if ad_rooms == 0:
            ad_rooms = 1

        # Цена
        if subscription.min_price is not None and ad_price is not None and ad_price < subscription.min_price:
            return False
        if subscription.max_price is not None and ad_price is not None and ad_price > subscription.max_price:
            return False

        # Количество комнат
        if subscription.min_rooms is not None and ad_rooms is not None and int(ad_rooms) < subscription.min_rooms:
            return False
        if subscription.max_rooms is not None and ad_rooms is not None and int(ad_rooms) > subscription.max_rooms:
            return False

        # Площадь проверяем только если она >0
        if ad_flat_area and subscription.min_flat is not None and ad_flat_area < subscription.min_flat:
            return False
        if ad_flat_area and subscription.max_flat is not None and ad_flat_area > subscription.max_flat:
            return False

        # Район
        if subscription.district not in (None, 'ANY') and ad_data.get('location') != subscription.district:
            return False

        # Метро
        if ad_metro_distance is not None and subscription.max_metro_distance is not None \
           and ad_metro_distance > subscription.max_metro_distance:
            return False

        return True

    except Exception as e:
        logger.error(f"Ошибка при проверке подписки {subscription.id}: {e}")
        return False

    except Exception as e:
        logger.error(f"Ошибка в фильтрации подписки: {e}", exc_info=True)
        return False


# @client.on(events.NewMessage(chats=channel_entities))
async def new_message_handler(event):
    bot = Bot(token=BOT_TOKEN)
    logger.info(f"Новое сообщение из канала: {event.chat.username or event.chat.title}")

    if event.message:
        text = event.message.text or ""
        media_items = await download_media(event.message)
        # Обрабатываем текст с Yandex GPT
        contacts = await process_contacts(text)
        print(contacts)
        help_text = await asyncio.to_thread(process_text_with_gpt3, text)
        print(help_text)

        new_text = await asyncio.to_thread(process_text_with_gpt, text)
        print(new_text)

        new_text = new_text.replace("*", "\n")
        if not (help_text.strip().lower().startswith("да") or help_text.strip().lower().startswith("ответ: да")):
            new_text = 'нет'
        if contacts.strip().lower().startswith("нет") or contacts.strip().lower().startswith("ответ: нет"):
            new_text = 'нет'
        logger.info(f"Обработанный текст: {new_text}")

        # Сохраняем сообщение в базу данных
        message = await sync_to_async(MESSAGE.objects.create)(
            text=text,
            images=[item['path'] for item in media_items] if media_items else None,
            new_text=new_text
        )

        if not (new_text.lower() in ['нет', 'нет.']):
            new_text += "\nКонтакты: " + contacts

            address = process_text_with_gpt_adress(new_text)
            coords = get_coords_by_address(address)

            def parse_flat_area(value):
                try:
                    if isinstance(value, str):
                        value = ''.join(c for c in value if c.isdigit())
                        return int(value) if value else None
                    return int(value) if value is not None else None
                except (ValueError, TypeError):
                    return None

            flat_area = parse_flat_area(process_text_with_gpt_sq(new_text))

            info = await sync_to_async(INFO.objects.create)(
                message=message,
                price=process_text_with_gpt_price(new_text),
                count_meters_flat=flat_area,
                count_meters_metro=find_nearest_metro(*coords),
                location=get_district_by_coords(*coords),
                adress=address,
                rooms=process_text_with_gpt_rooms(new_text)
            )

            # Уведомляем подписчиков
            asyncio.create_task(check_subscriptions_and_notify(info))

        # Отправляем результат в Telegram-канал
        if new_text.lower() not in ['нет', 'нет.']:
            if media_items:
                await send_media_group(bot, TELEGRAM_CHANNEL_ID, new_text, media_items)
            else:
                await bot.send_message(chat_id=TELEGRAM_CHANNEL_ID, text=new_text)

        # Задержка между сообщениями
        await asyncio.sleep(5)


def check_running():
    pid_file = "bot.pid"
    if os.path.exists(pid_file):
        with open(pid_file, "r") as f:
            old_pid = f.read()
        if os.path.exists(f"/proc/{old_pid}"):  # Для Linux
            print("Already running!")
            sys.exit(1)
        # Для Windows (альтернатива):
        try:
            os.kill(int(old_pid), 0)  # Проверяем, жив ли процесс
            sys.exit(1)
        except (ProcessLookupError, ValueError):
            pass  # Процесс умер, можно продолжать

    with open(pid_file, "w") as f:
        f.write(str(os.getpid()))


async def main():
    check_running()
    try:
        await client.connect()
        if not await client.is_user_authorized():
            await client.send_code_request(PHONE_NUMBER)
            code = input('Введите код из Telegram: ')
            try:
                await client.sign_in(PHONE_NUMBER, code)
            except telethon.errors.SessionPasswordNeededError:
                password = os.getenv('TELEGRAM_PASSWORD')
                await client.sign_in(password=password)

        # ✅ Получаем сущности каналов по username
        CHANNEL_USERNAMES = [
            "keystomoscow",
            "arendamsc",
            "onmojetprogat",
            "loltestneedxenaship",
            "arendamsk_mo",
            "lvngrm_msk",
            "Sdat_Kvartiru0",
            "bestflats_msk",
            "nebabushkin_msk",
        ]

        try:
            channel_entities = await asyncio.gather(*[client.get_entity(username) for username in CHANNEL_USERNAMES])
        except Exception as e:
            logger.error(f"Ошибка при получении каналов: {e}")
            return
    finally:
        if os.path.exists("bot.pid"):
            os.unlink("bot.pid")

    # ✅ Регистрируем обработчик событий вручную
    @client.on(events.NewMessage(chats=channel_entities))
    async def handler_wrapper(event):
        await new_message_handler(event)

    async with client:
        logger.info("Бот запущен и слушает каналы...")
        await client.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())