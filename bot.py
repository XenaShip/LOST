import asyncio
import logging
import re
from telegram import InputMediaVideo
import telethon
import django
from telegram import Bot, InputMediaPhoto
from telegram.error import RetryAfter, BadRequest
from telethon import TelegramClient, events
from dotenv import load_dotenv
from asgiref.sync import sync_to_async
import os
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

from main.models import  MESSAGE, INFO, Subscription  # Используем новую модель

# Настройка логгера
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)
processed_group_ids = set()      # (chat_id, grouped_id)
processed_message_ids = set()


bot2 = Bot(token=os.getenv("TOKEN3"))
# Конфигурация
PHONE_NUMBER = os.getenv('PHONE_NUMBER')
TELEGRAM_PASSWORD = os.getenv('TELEGRAM_PASSWORD')
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
SESSION_NAME = "session_name_lost"
METRO_CLOSE_MAX_METERS = int(os.getenv("METRO_CLOSE_MAX_METERS", "1200"))
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


async def process_contacts(text: str) -> str | None:
    raw_contact = await asyncio.to_thread(process_text_with_gpt2, text)
    print('process')
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


def _is_non_empty_file(path: str) -> bool:
    try:
        return os.path.isfile(path) and os.path.getsize(path) > 0
    except Exception:
        return False

def build_post_text(base_text: str, contacts: str | None, add_quote: bool = True) -> str:
    """
    Возвращает финальный текст:
    — добавляет блок 'Контакты: ...' один раз (если его ещё нет и контакты валидные)
    — добавляет цитату с HTML-ссылкой на бота (если add_quote=True)
    — соблюдает двойные пустые строки между абзацами
    """
    text = base_text or ""
    # нормализуем переносы: двойные пустые строки между абзацами
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    text = "\n\n".join(lines)

    # добавим контакты, если их ещё нет
    if contacts and contacts.lower() not in ["нет", "нет."] and "Контакты:" not in text:
        text += "\n\nКонтакты: " + contacts

    if add_quote:
        text += (
            "\n\n— <i>Настройте фильтры в "
            "<a href='https://t.me/arendatoriy_find_bot'>боте</a> "
            "и получайте только подходящие варианты</i>"
        )
    return text

async def send_media_group(bot, chat_id, text, media_items, parse_mode: str = "HTML"):
    if not media_items:
        await bot.send_message(chat_id, text, parse_mode=parse_mode)
        return

    media_group, open_files, valid_paths = [], [], []

    for item in media_items:
        file_path = item.get("path")
        file_type = item.get("type")
        if not file_path or not _is_non_empty_file(file_path):
            continue
        try:
            f = open(file_path, "rb")
        except Exception:
            continue

        open_files.append(f)
        valid_paths.append((file_path, file_type))
        caption = text if len(media_group) == 0 else None

        if file_type == "photo":
            media_group.append(InputMediaPhoto(media=f, caption=caption, parse_mode=parse_mode))
        else:
            media_group.append(InputMediaVideo(media=f, caption=caption, parse_mode=parse_mode))

    if not media_group:
        await bot.send_message(chat_id, text, parse_mode=parse_mode)
        return

    try:
        if len(media_group) == 1:
            file_path, file_type = valid_paths[0]
            try:
                if open_files:
                    open_files[0].close()
            except Exception:
                pass
            open_files = []

            if not _is_non_empty_file(file_path):
                await bot.send_message(chat_id, text, parse_mode=parse_mode)
                return

            with open(file_path, "rb") as fresh_f:
                if file_type == "photo":
                    await bot.send_photo(chat_id, fresh_f, caption=text, parse_mode=parse_mode)
                else:
                    await bot.send_video(chat_id, fresh_f, caption=text, parse_mode=parse_mode)
        else:
            await bot.send_media_group(chat_id=chat_id, media=media_group)

    except BadRequest as e:
        # отправим хотя бы текст, чтобы не терять пост
        await bot.send_message(chat_id, text, parse_mode=parse_mode)
    finally:
        for f in open_files:
            try:
                f.close()
            except Exception:
                pass


async def check_subscriptions_and_notify(info_instance, contacts):
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
    matched_users = set()
    for subscription in subscriptions:
        is_match = await sync_to_async(is_ad_match_subscription)(ad_data, subscription)
        if is_match and subscription.user_id not in matched_users:
            matched_users.add(subscription.user_id)
            await send_notification(subscription.user_id, ad_data, info_instance.message, contacts)

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


async def send_notification(user_id: int, ad_data: dict, message, contacts):
    """
    Отправка уведомления пользователю с поддержкой URL изображений (python-telegram-bot).
    """
    try:
        # Базовый текст из БД (уже отформатирован в new_message_handler)
        safe_text = message.new_text or ""

        # Добавим контакты и цитату, если ещё не добавлены здесь
        # (на всякий случай делаем это и в уведомлениях — вдруг текст в БД был без них)
        safe_text = build_post_text(safe_text, contacts, add_quote=True)

        media_paths = ad_data.get('images') or []
        media_group = []

        for idx, media_path in enumerate(media_paths[:10]):
            caption = safe_text if idx == 0 else None

            if str(media_path).startswith("http"):
                media_group.append(InputMediaPhoto(media=media_path, caption=caption, parse_mode="HTML"))
            elif os.path.exists(media_path):
                media_group.append(InputMediaPhoto(media=open(media_path, "rb"), caption=caption, parse_mode="HTML"))

        await asyncio.sleep(5)

        if media_group:
            if len(media_group) == 1:
                # одиночное фото
                await bot2.send_photo(chat_id=user_id, photo=media_group[0].media, caption=safe_text, parse_mode="HTML")
            else:
                # альбом — parse_mode задан внутри каждого InputMediaPhoto
                await bot2.send_media_group(chat_id=user_id, media=media_group)
        else:
            await bot2.send_message(chat_id=user_id, text=safe_text, parse_mode="HTML")

        logger.info(f"[NOTIFY] Отправлено объявление пользователю {user_id}")

    except RetryAfter as e:
        logger.warning(f"[NOTIFY] Flood control, повтор через {e.timeout} сек.")
        await asyncio.sleep(e.timeout)
        await send_notification(user_id, ad_data, message, contacts)  # не забудь передать contacts
    except Exception as e:
        logger.error(f"[NOTIFY] Ошибка при отправке уведомления пользователю {user_id}: {e}", exc_info=True)


def is_ad_match_subscription(ad_data, subscription):
    """
    Соответствие объявления подписке (под новые кнопки цены):
      ЦЕНА:
        1) "До 35 000₽"         -> min=None,  max=35000
        2) "35–65 тыс. ₽"       -> min=35000, max=65000
        3) "50–100 тыс. ₽"      -> min=50000, max=100000
        4) "Не важно"           -> min=None,  max=None  (фильтр цены не применяется)

      Другое:
        - Комнаты: 0 -> 1 (студия = 1 комната)
        - Площадь: сверяем только если > 0
        - Район: игнорируем, если None/ 'ANY'
        - Метро: объявление подходит, если расстояние <= лимита
    """
    try:
        ad_price = safe_parse_number(ad_data.get('price'))
        ad_rooms = safe_parse_number(ad_data.get('rooms'))
        ad_flat_area = safe_parse_number(ad_data.get('count_meters_flat'))
        ad_metro_distance = safe_parse_number(ad_data.get('count_meters_metro'))

        # Студия как 1 комната
        if ad_rooms == 0:
            ad_rooms = 1

        # ---------- ЦЕНА ----------
        # Если выбрано "Не важно" -> min_price/max_price должны быть None
        min_price = getattr(subscription, 'min_price', None)
        max_price = getattr(subscription, 'max_price', None)

        if ad_price is not None:
            if min_price is not None and ad_price < min_price:
                return False
            if max_price is not None and ad_price > max_price:
                return False
        # Если ad_price None — не валим объявление по цене, оставляем шанс другим фильтрам

        # ---------- КОМНАТЫ ----------
        if ad_rooms is not None:
            if getattr(subscription, 'min_rooms', None) is not None and int(ad_rooms) < subscription.min_rooms:
                return False
            if getattr(subscription, 'max_rooms', None) is not None and int(ad_rooms) > subscription.max_rooms:
                return False

        # ---------- ПЛОЩАДЬ ----------
        if ad_flat_area and ad_flat_area > 0:
            if getattr(subscription, 'min_flat', None) is not None and ad_flat_area < subscription.min_flat:
                return False
            if getattr(subscription, 'max_flat', None) is not None and ad_flat_area > subscription.max_flat:
                return False

        # ---------- РАЙОН ----------
        sub_district = getattr(subscription, 'district', None)
        if sub_district not in (None, 'ANY'):
            # Пример: в объявлении район хранится в ad_data['location']
            if ad_data.get('location') != sub_district:
                return False

        # ---------- МЕТРО ----------
        # Условие: объявление подходит, если фактическое расстояние <= максимального лимита подписки
        max_metro = getattr(subscription, 'max_metro_distance', None)
        if ad_metro_distance is not None and max_metro is not None:
            if ad_metro_distance > max_metro:
                return False

        return True

    except Exception as e:
        logger.error(f"Ошибка в фильтрации подписки: {e}", exc_info=True)
        return False



async def extract_text_from_event(event):
    """
    Если сообщение — часть альбома (grouped_id), собираем подписи со всех
    сообщений альбома и берём первую непустую. Иначе — обычный text/caption.
    """
    msg = event.message
    if getattr(msg, "grouped_id", None):
        # Небольшая задержка, чтобы остальные части альбома успели прилететь
        # (по желанию — можно убрать)
        # import asyncio
        # await asyncio.sleep(0.5)

        album_msgs = await client.get_messages(msg.chat_id, min_id=msg.id - 50, max_id=msg.id + 50)
        album_msgs = [m for m in album_msgs if m and m.grouped_id == msg.grouped_id]
        album_msgs.sort(key=lambda x: x.id)
        for m in album_msgs:
            t = (m.text or "").strip()
            if t:
                return t
    return (msg.text or "").strip()

# @client.on(events.NewMessage(chats=channel_entities))
async def new_message_handler(event):
    bot = Bot(token=BOT_TOKEN)
    logger.info(f"Новое сообщение из канала: {event.chat.username or event.chat.title}")

    if event.message:
        msg = event.message

        key_msg = (msg.chat_id, msg.id)
        if key_msg in processed_message_ids:
            logger.info('Skip: already processed this message id')
            return
        processed_message_ids.add(key_msg)

        if getattr(msg, "grouped_id", None):
            key_album = (msg.chat_id, msg.grouped_id)
            if key_album in processed_group_ids:
                logger.info('Skip: album already processed')
                return
            processed_group_ids.add(key_album)
        text = await extract_text_from_event(event)
        media_items = await download_media(event.message)
        contacts = await process_contacts(text)
        if contacts and contacts.startswith("tg://user?id="):
            try:
                user_id = contacts.split("=", 1)[1]
            except Exception:
                user_id = None

            if user_id:
                fixed = await get_username_by_id(user_id)
                if fixed:
                    contacts = fixed  # заменяем на читабельный @username/ссылку
                else:
                    logger.info("Пропуск: контакт tg://… не удалось преобразовать повторно.")
                    return  # не отправляем это уведомление/пост
            else:
                logger.info("Пропуск: некорректный формат tg://user?id=…")
                return
        help_text = await asyncio.to_thread(process_text_with_gpt3, text)
        new_text = await asyncio.to_thread(process_text_with_gpt, text)
        new_text = new_text.replace("*", "\n\n")
        lines = [line.strip() for line in new_text.split("\n") if line.strip()]
        new_text = "\n\n".join(lines)
        # БЫЛО: строгая проверка на "да"/"ответ: да"
        if not _is_yes(help_text):
            new_text = 'нет'
        if _is_no(contacts):
            new_text = 'нет'
        print(new_text)

        # Сохраняем сообщение в базу данных
        message = await sync_to_async(MESSAGE.objects.create)(
            text=text,
            images=[item['path'] for item in media_items] if media_items else None,
            new_text=new_text
        )

        if not (new_text.lower() in ['нет', 'нет.']):
            if not (new_text.lower() in ['нет', 'нет.']):
                new_text += "\n\nКонтакты: " + contacts

                # 📌 Добавляем цитату в конце
                new_text += (
                    "\n\n— <i>Настройте фильтры в "
                    "<a href='https://t.me/arendatoriy_find_bot'>боте</a> "
                    "и получайте только подходящие варианты</i>"
                )
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
            asyncio.create_task(check_subscriptions_and_notify(info, contacts))

        # Отправляем результат в Telegram-канал
        if new_text.lower() not in ['нет', 'нет.']:
            try:
                if media_items:
                    await send_media_group(bot, TELEGRAM_CHANNEL_ID, new_text, media_items)
                else:
                    await bot.send_message(
                        chat_id=TELEGRAM_CHANNEL_ID,
                        text=new_text,
                        parse_mode="HTML"
                    )
                logger.info(f"[CHANNEL] Пост отправлен в {TELEGRAM_CHANNEL_ID}")
            except Exception as e:
                logger.error(f"[CHANNEL] Ошибка отправки в канал {TELEGRAM_CHANNEL_ID}: {e}", exc_info=True)


def _is_yes(s: str | None) -> bool:
    return bool(s) and re.match(r'^(да|yes|y|true)\b', s.strip(), flags=re.I)

def _is_no(s: str | None) -> bool:
    return bool(s) and re.match(r'^(нет|no|n|false)\b', s.strip(), flags=re.I)



async def main():
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

        CHANNEL_USERNAMES = [
            "keystomoscow", "arendamsc", "onmojetprogat", "loltestneedxenaship",
            "arendamsk_mo", "lvngrm_msk", "Sdat_Kvartiru0", "bestflats_msk", "nebabushkin_msk",
        ]
        try:
            channel_entities = await asyncio.gather(
                *[client.get_entity(u) for u in CHANNEL_USERNAMES]
            )
        except Exception as e:
            logger.error(f"Ошибка при получении каналов: {e}")
            return

        @client.on(events.NewMessage(chats=channel_entities))
        async def handler_wrapper(event):
            await new_message_handler(event)

        async with client:
            logger.info("Бот запущен и слушает каналы...")
            await client.run_until_disconnected()

    finally:
        # снимаем PID-лок ТОЛЬКО при полном завершении работы бота
        if os.path.exists("bot.pid"):
            os.unlink("bot.pid")


if __name__ == "__main__":
    asyncio.run(main())