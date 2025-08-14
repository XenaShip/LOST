import asyncio
import os
import aiohttp
import logging
import time
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message
from aiogram.filters import Command
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from telegram import InputMediaPhoto
from telegram.error import RetryAfter
from webdriver_manager.chrome import ChromeDriverManager
from django.conf import settings
from asgiref.sync import sync_to_async
import django
from yandex_cloud_ml_sdk import YCloudML
from aiogram.types import InputMediaPhoto
import undetected_chromedriver as uc
import time
import aiogram.utils.markdown as md
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from district import get_coords_by_address, get_district_by_coords
from make_info import process_text_with_gpt_adress, process_text_with_gpt_price, process_text_with_gpt_sq, \
    process_text_with_gpt_rooms
from meters import find_nearest_metro
from proccess import process_text_with_gpt2, process_text_with_gpt

# Настроим Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

# Импортируем модель MESSAGE
from main.models import MESSAGE, INFO, Subscription

# Загружаем переменные окружения
load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
bot = Bot(token=TOKEN)
dp = Dispatcher()
TELEGRAM_CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID")
# Настройка логирования
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

bot2 = Bot(token=os.getenv("TOKEN3"))

async def send_images_with_text(bot, chat_id, text, images):
    """Отправляет изображения в Telegram, первое с текстом, остальные без."""
    media_group = []
    for index, img_url in enumerate(images):
        if index == 0:
            media_group.append(InputMediaPhoto(media=img_url, caption=text))  # Первое изображение с текстом
        else:
            media_group.append(InputMediaPhoto(media=img_url))

    if media_group:
        await bot.send_media_group(chat_id=chat_id, media=media_group)


from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def escape_md_v2(text):
    special_chars = r"_*[]()~`>#+-=|{}.!"
    return "".join(f"\\{char}" if char in special_chars else char for char in text)


def fetch_page_data(url):
    """Загружает страницу через undetected_chromedriver и извлекает текст и изображения"""
    from webdriver_manager.chrome import ChromeDriverManager
    from selenium.webdriver.chrome.service import Service

    options = uc.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument(
        "user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36")

    driver = None
    try:
        # Инициализация драйвера с автоматической установкой ChromeDriver
        driver = uc.Chrome(options=options, version_main=138)

        driver.set_page_load_timeout(60)
        logging.info(f"Открываю страницу: {url}")
        driver.get(url)

        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )

        # Прокрутка страницы
        for _ in range(3):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1)

        page_text = driver.find_element(By.TAG_NAME, "body").text

        images = []
        for img in driver.find_elements(By.TAG_NAME, "img"):
            src = img.get_attribute("src")
            if src and src.startswith(("http://", "https://")):
                images.append(src)
            if len(images) >= 10:
                break

        return page_text, images

    except Exception as e:
        logging.error(f"Ошибка при загрузке страницы: {str(e)}")
        return "", []
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass



@sync_to_async
def save_message_to_db(text, images, new_text):
    """Сохранение объявления в БД."""
    return MESSAGE.objects.create(text=text, images=images, new_text=new_text)



async def fetch_message_from_db():
    """Получение последнего сообщения из базы"""
    return await sync_to_async(lambda: MESSAGE.objects.last())()

async def download_images(images):
    """Загружает изображения и сохраняет ссылки в БД"""
    async with aiohttp.ClientSession() as session:
        filenames = []
        for index, img_url in enumerate(images):
            async with session.get(img_url) as response:
                if response.status == 200:
                    filenames.append(img_url)  # Сохраняем ссылки вместо файлов
        return filenames


@dp.message(Command("start"))
async def start_handler(message: Message):
    await message.answer("Привет! Отправь мне ссылку, и я сохраню текст и изображения.")

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

@dp.message()
async def message_handler(message: Message):
    url = message.text.strip()
    await message.answer("🔍 Обрабатываю страницу, подождите...")

    # Получаем текст, изображения и телефон
    text, images = fetch_page_data(url)

    if not text and not images:
        await message.answer("⚠️ Не удалось найти данные на странице.")
        return

    # Загружаем изображения
    image_urls = await download_images(images)

    # Обновляем текст через GPT
    new_text = await asyncio.to_thread(process_text_with_gpt, text)
    new_text = new_text.replace("*", " ")
    print(new_text)

    mmessage = await sync_to_async(MESSAGE.objects.create)(
        text=text,
        images=images if images else None,
        new_text=new_text + f' Контакты {url}'
    )
    if new_text != 'Нет' and new_text != 'Нет.':
        address = process_text_with_gpt_adress(new_text)
        coords = get_coords_by_address(address)

        # Преобразуем площадь в целое число
        def parse_flat_area(value):
            try:
                if isinstance(value, str):
                    # Удаляем все нецифровые символы и берем целую часть
                    value = ''.join(c for c in value if c.isdigit())
                    return int(value) if value else None
                return int(value) if value is not None else None
            except (ValueError, TypeError):
                return None

        flat_area = parse_flat_area(process_text_with_gpt_sq(new_text))

        info = await sync_to_async(INFO.objects.create)(
            message=mmessage,
            price=process_text_with_gpt_price(new_text),
            count_meters_flat=flat_area,  # Используем преобразованное значение
            count_meters_metro=find_nearest_metro(*coords),
            location=get_district_by_coords(*coords),
            adress=process_text_with_gpt_adress(new_text),
            rooms=process_text_with_gpt_rooms(new_text)
        )
        asyncio.create_task(check_subscriptions_and_notify(info))

    # Отправляем сообщение в канал
    media_group = [InputMediaPhoto(media=img_url) for img_url in image_urls[1:]]  # Пропускаем первое изображение

    if media_group:
        caption = f"{escape_md_v2(new_text)}\n📞 [Контакты]({escape_md_v2(url)})"
        media_group[0].caption = caption
        media_group[0].parse_mode = "MarkdownV2"
        await bot.send_media_group(chat_id=TELEGRAM_CHANNEL_ID, media=media_group)
    else:
        text = f"{escape_md_v2(new_text)}\n📞 [Контакты]({escape_md_v2(url)})"
        await bot.send_message(TELEGRAM_CHANNEL_ID, text, parse_mode="MarkdownV2")

    await message.answer("✅ Данные сохранены и отправлены!")


async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)



async def main():
    await asyncio.sleep(10)
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())