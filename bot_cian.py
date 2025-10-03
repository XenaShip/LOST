import asyncio
import os
import aiohttp
import logging
from aiogram import Bot, Dispatcher
from aiogram.types import Message
from aiogram.filters import Command
from dotenv import load_dotenv
from telegram import InputMediaPhoto
from telegram.error import RetryAfter
from asgiref.sync import sync_to_async
import django
from aiogram.types import InputMediaPhoto
import time
import undetected_chromedriver as uc
from aiogram.types import InputMediaPhoto
from aiogram.exceptions import TelegramRetryAfter
from dev_bot import process_text_with_gpt2
from district import get_coords_by_address, get_district_by_coords
from make_info import process_text_with_gpt_adress, process_text_with_gpt_price, process_text_with_gpt_sq, \
    process_text_with_gpt_rooms
from meters import find_nearest_metro
from proccess import process_text_with_gpt

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
    """
    Шлём максимум 8 фото, пропуская первые 2 (обычно логотипы CIAN).
    Первое реальное фото несёт caption; если фото нет — отправляем просто текст.
    В конец добавляем цитату с HTML-ссылкой на бота.
    """
    from aiogram.types import InputMediaPhoto

    quote = ("\n\n— <i>Настройте фильтры в "
             "<a href='https://t.me/arendatoriy_find_bot'>боте</a> "
             "и получайте только подходящие варианты</i>")

    base = escape_html(text or "")
    caption = base + quote

    usable = (images or [])[2:10]  # пропускаем 2, берём до 8
    if not usable:
        await bot.send_message(chat_id=chat_id, text=caption, parse_mode="HTML")
        return

    media_group = []
    for idx, img_url in enumerate(usable):
        if idx == 0:
            media_group.append(InputMediaPhoto(media=img_url, caption=caption, parse_mode="HTML"))
        else:
            media_group.append(InputMediaPhoto(media=img_url))

    if len(media_group) == 1:
        await bot.send_photo(chat_id=chat_id, photo=media_group[0].media, caption=caption, parse_mode="HTML")
    else:
        await bot.send_media_group(chat_id=chat_id, media=media_group)



from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


def escape_html(text: str) -> str:
    if text is None:
        return ""
    return (text
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;"))

def escape_attr(text: str) -> str:
    if text is None:
        return ""
    return (text
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#39;"))

def escape_md_v2(text):
    special_chars = r"_*[]()~`>#+-=|{}.!"
    return "".join(f"\\{char}" if char in special_chars else char for char in text)


import os
import re
import time
import logging

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def _create_uc_driver(version_main: int, headless: bool | None = None):
    """
    Стартует undetected_chromedriver c явным бинарём Chrome в контейнере.
    Если мы в Docker (или задан CHROME_BIN), принудительно headless и безопасные флаги.
    """
    in_docker = os.path.exists("/.dockerenv") or os.getenv("IN_DOCKER") == "1"
    chrome_bin = os.getenv("CHROME_BIN") or os.getenv("CHROMIUM_BIN")
    if in_docker:
        # в контейнере всегда headless
        headless = True if headless is None else headless
    else:
        # локально можно и без headless
        headless = False if headless is None else headless

    options = uc.ChromeOptions()
    if headless:
        options.add_argument("--headless=new")
    # безопасные флаги для root в контейнере
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-software-rasterizer")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-blink-features=AutomationControlled")
    # НЕ ставим кастомный user-agent

    extra_args = (os.getenv("CHROME_EXTRA_ARGS") or "").split()
    for a in extra_args:
        if a:
            options.add_argument(a)

    logging.warning(f"=== UC START: version_main={version_main}, headless={headless}, bin={chrome_bin or 'system'} ===")

    kwargs = dict(options=options, version_main=version_main, use_subprocess=True)
    if chrome_bin:
        # укажем явный бинарь Chrome, установленный в образ
        kwargs["browser_executable_path"] = chrome_bin

    driver = uc.Chrome(**kwargs)
    driver.set_page_load_timeout(60)
    return driver


def fetch_page_data(url: str):
    """
    Загружает страницу объявления и возвращает (page_text, image_urls).
    - Берём version_main из ENV (по умолчанию 141 — см. твой серверный лог).
    - Делаем одну автоматическую повторную попытку, если драйвер подскажет другую мажорную версию.
    - В контейнере принудительно headless + системный Chrome из CHROME_BIN.
    """
    try:
        version_main = int(os.getenv("UC_VERSION_MAIN", "141"))
    except ValueError:
        version_main = 141

    driver = None
    try:
        try:
            driver = _create_uc_driver(version_main=version_main)
        except Exception as e1:
            msg = str(e1)
            m = re.search(r"only supports Chrome version\s+(\d+)", msg)
            if m:
                hinted = int(m.group(1))
                logging.warning(f"Повторный запуск UC с подсказанной версией: {hinted}")
                driver = _create_uc_driver(version_main=hinted)
            else:
                logging.error(f"Не удалось запустить драйвер: {msg}")
                return "", []

        logging.info(f"Открываю страницу: {url}")
        driver.get(url)

        WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        for _ in range(3):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(0.8)

        page_text = driver.find_element(By.TAG_NAME, "body").text or ""

        images = []
        for img in driver.find_elements(By.TAG_NAME, "img"):
            src = img.get_attribute("src")
            if src and src.startswith(("http://", "https://")) and "data:image" not in src:
                images.append(src)
            if len(images) >= 12:
                break

        # Фолбэк на мобильную версию, если совсем пусто
        if not page_text.strip() and not images and "://www.cian.ru/" in url:
            try:
                m_url = url.replace("://www.cian.ru/", "://m.cian.ru/")
                driver.get(m_url)
                WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
                for _ in range(2):
                    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(0.6)
                page_text = driver.find_element(By.TAG_NAME, "body").text or ""
                images = []
                for img in driver.find_elements(By.TAG_NAME, "img"):
                    src = img.get_attribute("src")
                    if src and src.startswith(("http://", "https://")) and "data:image" not in src:
                        images.append(src)
                    if len(images) >= 12:
                        break
            except Exception as e_mb:
                logging.warning(f"Мобильная версия не помогла: {e_mb}")

        return page_text.strip(), images

    except Exception as e:
        logging.error(f"Ошибка при загрузке страницы: {e}")
        return "", []
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
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
    Отправка уведомления пользователю (aiogram v3):
    - пропускаем первые 2 картинки (логотипы),
    - берём максимум 8,
    - caption кладём на первое реальное фото,
    - добавляем в конец цитату с ссылкой на бота (HTML),
    - если картинок нет — шлём только текст.
    """
    import os
    import asyncio
    from aiogram.types import InputMediaPhoto
    try:
        from aiogram.exceptions import TelegramRetryAfter
    except Exception:
        TelegramRetryAfter = Exception  # на случай старых версий

    safe_text = message.new_text or ""

    # Добавим контакты, если их нет в тексте
    if "Контакты" not in safe_text:
        contacts = await asyncio.to_thread(process_text_with_gpt2, message.text)
        if contacts and contacts.lower() not in ['нет', 'нет.']:
            safe_text += " Контакты: " + contacts

    # Собираем итоговый HTML-caption
    quote = ("\n\n— <i>Настройте фильтры в "
             "<a href='https://t.me/arendatoriy_find_bot'>боте</a> "
             "и получайте только подходящие варианты</i>")
    caption_html = escape_html(safe_text) + quote

    media_paths = ad_data.get('images') or []
    usable = media_paths[2:10]  # пропускаем 2, максимум 8

    media_group = []
    for idx, media_path in enumerate(usable):
        cap = caption_html if idx == 0 else None
        if isinstance(media_path, str) and media_path.startswith("http"):
            item = InputMediaPhoto(media=media_path, caption=cap)
            if cap:
                item.parse_mode = "HTML"
            media_group.append(item)
        elif media_path and os.path.exists(media_path):
            item = InputMediaPhoto(media=open(media_path, "rb"), caption=cap)
            if cap:
                item.parse_mode = "HTML"
            media_group.append(item)

    try:
        if media_group:
            if len(media_group) == 1:
                await bot2.send_photo(chat_id=user_id, photo=media_group[0].media, caption=caption_html, parse_mode="HTML")
            else:
                await bot2.send_media_group(chat_id=user_id, media=media_group)
        else:
            await bot2.send_message(chat_id=user_id, text=caption_html, parse_mode="HTML")

        logger.info(f"[NOTIFY] Отправлено объявление пользователю {user_id}")
    except TelegramRetryAfter as e:
        logger.warning(f"[NOTIFY] Flood control, повтор через {getattr(e, 'timeout', 1)} сек.")
        await asyncio.sleep(getattr(e, 'timeout', 1))
        await send_notification(user_id, ad_data, message)
    except Exception as e:
        logger.error(f"[NOTIFY] Ошибка при отправке уведомления пользователю {user_id}: {e}", exc_info=True)


async def send_to_channel(bot, channel_id: int, new_text: str, url: str, image_urls: list[str]):
    """
    Публикуем в канал:
    - пропускаем первые 2 изображения (логотипы),
    - берём максимум 8,
    - caption ставим на первое реальное фото,
    - добавляем цитату с HTML-ссылкой на бота,
    - используем parse_mode="HTML".
    """
    from aiogram.types import InputMediaPhoto

    base = escape_html(new_text or "")
    link = f"<a href='{escape_attr(url)}'>Контакты</a>"
    quote = ("\n\n— <i>Настройте фильтры в "
             "<a href='https://t.me/arendatoriy_find_bot'>боте</a> "
             "и получайте только подходящие варианты</i>")
    caption = f"{base}\n📞 {link}{quote}"

    usable = (image_urls or [])[2:10]

    if usable:
        media_group = []
        for idx, img in enumerate(usable):
            if idx == 0:
                media_group.append(InputMediaPhoto(media=img, caption=caption, parse_mode="HTML"))
            else:
                media_group.append(InputMediaPhoto(media=img))

        if len(media_group) == 1:
            await bot.send_photo(chat_id=channel_id,
                                 photo=media_group[0].media,
                                 caption=caption,
                                 parse_mode="HTML")
        else:
            await bot.send_media_group(chat_id=channel_id, media=media_group)
    else:
        await bot.send_message(chat_id=channel_id, text=caption, parse_mode="HTML")


@dp.message()
async def message_handler(message: Message):
    # 1) Берём URL из сообщения и подтверждаем старт
    url = (message.text or "").strip()
    if not url:
        await message.answer("Пришлите ссылку на объявление CIAN.")
        return

    await message.answer("🔍 Обрабатываю страницу, подождите...")

    # 2) Парсим страницу: сырой текст + src картинок (до 10)
    text, images = fetch_page_data(url)
    if not text and not images:
        await message.answer("⚠️ Не удалось найти данные на странице.")
        return

    # 3) (Опционально) «скачиваем» картинки — у тебя сохраняются URL
    image_urls = await download_images(images)

    # 4) Готовим человекочитаемый текст объявления (без Markdown-звёздочек и мусора)
    new_text = await asyncio.to_thread(process_text_with_gpt, text)  # CPU-bound → в поток
    # убираем * и схлопываем пустые строки
    new_text = new_text.replace("*", " ")
    lines = [ln.strip() for ln in new_text.splitlines() if ln.strip()]
    new_text = "\n\n".join(lines)

    # 5) Сохраняем сообщение в БД (как и раньше — с добавлением "Контакты <url>")
    mmessage = await sync_to_async(MESSAGE.objects.create)(
        text=text,
        images=images if images else None,
        new_text=new_text + f" Контакты {url}",
    )

    # 6) Извлекаем структурку для DEVINFO и сохраняем
    if new_text not in ("Нет", "Нет."):
        address = process_text_with_gpt_adress(new_text)
        coords = get_coords_by_address(address)

        def parse_flat_area(value):
            """Преобразуем площадь к int, если пришла строка с 'м²' и пр."""
            try:
                if isinstance(value, str):
                    digits = "".join(c for c in value if c.isdigit())
                    return int(digits) if digits else None
                return int(value) if value is not None else None
            except (ValueError, TypeError):
                return None

        flat_area = parse_flat_area(process_text_with_gpt_sq(new_text))

        info = await sync_to_async(INFO.objects.create)(
            message=mmessage,
            price=process_text_with_gpt_price(new_text),
            count_meters_flat=flat_area,
            count_meters_metro=find_nearest_metro(*coords),
            location=get_district_by_coords(*coords),
            adress=address,
            rooms=process_text_with_gpt_rooms(new_text),
        )
        # Асинхронно проверяем подписки и шлём уведомления
        asyncio.create_task(check_subscriptions_and_notify(info))  # шлёт с HTML-цитатой и срезом 2:10

    # 7) Публикуем в канал (функция уже делает HTML-цитату и берёт фото [2:10])
    await send_to_channel(bot, TELEGRAM_CHANNEL_ID, new_text, url, image_urls)  # HTML+quote внутри функции. :contentReference[oaicite:2]{index=2}

    # 8) Ответ пользователю
    await message.answer("✅ Данные сохранены и отправлены!")


async def main():
    await asyncio.sleep(10)
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())