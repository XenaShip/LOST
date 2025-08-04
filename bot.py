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
            "text": """
                Вы— помощник, который превращает объявление об аренде квартиры или комнаты в структурированный шаблон.

                Если текст не является объявлением об аренде, просто верните слово нет.

                Если это объявление об аренде, выведите точно в таком формате (каждая строка - новый пункт):

                🏠 Комнаты: <количество комнат или описание комнат>*
                💰 Цена: <цена + условия оплаты>*
                📍 Адрес: <улица, метро или район>*
                ⚙️ Условия: <дата заселения, прочие условия>*
                📝 Описание: <дополнительное описание, рядом инфраструктура, ограничения>

                Ничего больше не добавляйте: ни «Контакты:», ни лишних эмодзи, ни ссылок. '*' - обязательный символ в шаблоне
                """,
        },
        {
            "role": "user",
            "text": text,
        },
    ]
    result = (
        sdk.models.completions("yandexgpt").configure(temperature=0.5).run(messages_1)
    )
    return result.text


def process_text_with_gpt3(text):
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
            "text": """
                Вы — надёжный классификатор объявлений об аренде квартир и комнат в Москве.
                Вашей задачей является однозначно определить: является ли этот текст **объявлением об аренде** (сдаётся квартира или комната физическим лицом, без рекламы агентств и без продажи). 

                Критерии «аренда»:
                - В тексте присутствуют слова «сдаётся», «сдаются», «сдаю», «аренда», «арендую».
                - Указана цена или диапазон цен.
                - Есть контакт (телефон или упоминание Telegram‑ссылки).
                - Нет слов «продаётся», «продаю», «в продажу», «продажа», «ищу квартиру», «резюме».

                **Инструкция**:  
                – Если текст **является** объявлением об аренде — ответьте ровно `Да`.  
                – Если текст **не является** объявлением об аренде — ответьте ровно `Нет`.  
                – Ничего больше не выводите, только одно слово (с заглавной буквы).
                """,
        },
        {
            "role": "user",
            "text": text,
        },
    ]
    result = (
        sdk.models.completions("yandexgpt").configure(temperature=0.5).run(messages_1)
    )
    return result.text


def text_with_gpt(text):
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
            "text": "какой сегодня год?",
        },
        {
            "role": "user",
            "text": text,
        },
    ]
    result = (
        sdk.models.completions("yandexgpt").configure(temperature=0.5).run(messages_1)
    )
    return result.text


def process_text_with_gpt2(text):
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
            "text": "Извлекай контактную информацию из текста объявлений и преобразуй её в чистую Telegram-ссылку. Если ссылка на циан, то оставляй ссылку такой же .НЕ УКАЗЫВАЙ ССЫЛКИ НА ДРУГИЕ РЕСУРСЫ И КАНАЛЫ, БОТОВ, ТОЛЬКО НА ПРОФИЛЬ "
                    "Правила обработки:\n"
                    "1. Если найдешь фразы 'написать', 'контакты:', 'связь:' или подобные - извлеки контактные данные\n"
                    "2. Для Telegram контактов возвращай только чистую ссылку в формате https://t.me/XXXX или tg://user?id=XXXXXXX \n"
                    "3. Если контакт указан как @username - оставь так же\n"
                    "4. Телефонные номера и другие контакты оставляй без изменений\n"
                    "5. Всё остальное содержимое объявления не изменяй\n\n"
                    "6. Если ссылка на 'https://www.cian.ru/', то оставляй без изменений\n"
                    "7. Возвращай только одну ссылку или номер телефона на профиль человека, никаких ссылок на другие боты и каналы\n"
                    "8. Если указан номер телефона, извлекай только его, ссылки не нужны\n"
                    "Примеры преобразования:\n"
                    "1. 'Контакты: [Анна](tg://user?id=12345)' → 'tg://user?id=12345'\n"
                    "2. 'Написать: @ivanov' → @ivanov\n"
                    "3. 'Телефон: +79161234567' → оставить без изменений\n"
                    "4. 'Контакты: [Менеджер](https://t.me/manager)' → https://t.me/manager\n\n"
                    "5. 'Циан, контакты (https://www.cian.ru/rent/flat/319392264) уровень доверия низкий ⚠️ (http://t.me/lvngrm_msk/26)выложить квартиру бесплатно (http://t.me/lvngrm_bot?start=PM)' → https://www.cian.ru/rent/flat/319392264\n\n"
                    "Важно: возвращай только ОДНУ саму ссылку, без дополнительного текста и форматирования! Если контактов нет - ответь 'нет'"
                    "пример: 'нет'"
        },
        {
            "role": "user",
            "text": text,
        },
    ]
    result = (
        sdk.models.completions("yandexgpt").configure(temperature=0.5).run(messages_1)
    )
    return result.text


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
    # Получаем все активные подписки
    subscriptions = await sync_to_async(list)(Subscription.objects.filter(is_active=True))

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
        if await sync_to_async(is_ad_match_subscription)(ad_data, subscription):
            await send_notification(subscription.user_id, ad_data, info_instance.message)


def escape_markdown(text: str) -> str:
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    return re.sub(f'([{re.escape(escape_chars)}])', r'\\\1', text)


def acquire_lock():
    lock_file = open("bot.lock", "w")
    try:
        fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except IOError:
        print("Another instance is already running. Exiting.")
        sys.exit(1)
    return lock_file


async def send_notification(user_id: int, ad_data: dict, message):
    try:
        contacts = await process_contacts(message.text)
        raw_text = message.new_text + " Контакты: " + contacts
        safe_text = raw_text

        # Ограничение длины подписи для media_group
        MAX_CAPTION_LENGTH = 1024
        if len(safe_text) > MAX_CAPTION_LENGTH:
            safe_text = safe_text[:MAX_CAPTION_LENGTH - 3] + "..."

        media_paths = ad_data.get('images') or []

        if media_paths and isinstance(media_paths, list):
            media_group = []
            open_files = []
            for idx, media_path in enumerate(media_paths[:10]):
                if not os.path.exists(media_path):
                    continue

                f = open(media_path, "rb")
                open_files.append(f)

                is_video = media_path.lower().endswith(('.mp4', '.mov', '.avi'))
                caption = safe_text if idx == 0 else None

                if is_video:
                    media = InputMediaVideo(media=f, caption=caption)
                else:
                    media = InputMediaPhoto(media=f, caption=caption)

                media_group.append(media)

            if len(media_group) == 1:
                m = media_group[0]
                if isinstance(m, InputMediaPhoto):
                    await bot2.send_photo(chat_id=user_id, photo=m.media, caption=safe_text)
                else:
                    await bot2.send_video(chat_id=user_id, video=m.media, caption=safe_text)
            elif media_group:
                await bot2.send_media_group(chat_id=user_id, media=media_group)

            for f in open_files:
                f.close()

        else:
            # Если нет медиа — обычное сообщение
            MAX_MESSAGE_LENGTH = 4096
            text_msg = safe_text[:MAX_MESSAGE_LENGTH - 3] + "..." if len(safe_text) > MAX_MESSAGE_LENGTH else safe_text
            await bot2.send_message(chat_id=user_id, text=text_msg)

    except RetryAfter as e:
        await asyncio.sleep(e.timeout)
        await send_notification(user_id, ad_data, message)
    except Exception as e:
        logger.error(f"Ошибка при отправке уведомления: {e}", exc_info=True)


def is_ad_match_subscription(ad_data, subscription):
    """Синхронная функция проверки соответствия подписки"""
    try:
        # Функция для преобразования строки с запятой в число
        def parse_number(value):
            if value is None:
                return None
            if isinstance(value, str):
                # Заменяем запятую на точку и удаляем пробелы
                value = value.replace(',', '.').strip()
            try:
                return float(value)
            except (ValueError, TypeError):
                return None

        # Преобразуем значения в числа (если они не None)
        ad_price = parse_number(ad_data['price'])
        ad_rooms = parse_number(ad_data['rooms'])
        ad_flat_area = parse_number(ad_data.get('count_meters_flat'))
        ad_metro_distance = parse_number(ad_data.get('count_meters_metro'))

        # Проверка цены
        if subscription.min_price is not None and ad_price is not None and ad_price < subscription.min_price:
            return False
        if subscription.max_price is not None and ad_price is not None and ad_price > subscription.max_price:
            return False

        # Проверка количества комнат (используем int, так как комнаты целые)
        if subscription.min_rooms is not None and ad_rooms is not None and int(ad_rooms) < subscription.min_rooms:
            return False
        if subscription.max_rooms is not None and ad_rooms is not None and int(ad_rooms) > subscription.max_rooms:
            return False

        # Проверка площади квартиры
        if subscription.min_flat is not None and ad_flat_area is not None and ad_flat_area < subscription.min_flat:
            return False
        if subscription.max_flat is not None and ad_flat_area is not None and ad_flat_area > subscription.max_flat:
            return False

        # Проверка района
        if subscription.district != 'ANY' and ad_data.get('location') != subscription.district:
            return False

        # Проверка расстояния до метро
        if (ad_metro_distance is not None and
                subscription.max_metro_distance is not None and
                ad_metro_distance > subscription.max_metro_distance):
            return False

        return True
    except Exception as e:
        print(f"Ошибка при проверке соответствия подписки: {e}")
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
            "keystomoscow"
            "arendamsc",
            "onmojetprogat",
            "loltestneedxenaship",
            "arendamsk_mo",
            "lvngrm_msk",
            "Sdat_Kvartiru0",
            "bestflats_msk",
            "nebabushkin_msk",
            "keystomoscow",
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