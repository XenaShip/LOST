import logging
import os
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

from yandex_cloud_ml_sdk import YCloudML


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

                Если текст не является объявлением об аренде или в тексте есть имя Лидия Лиханская, просто верните слово нет.

                Если это объявление об аренде, выведите точно в таком формате (каждая строка— новый пункт):

                🏠 Комнаты: <количество комнат или описание комнат*>
                💰 Цена: <цена + условия оплаты*>
                📍 Адрес: <улица, метро или район*>
                ⚙️ Условия: <дата заселения, прочие условия*>
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
                – Если текст **не является** объявлением об аренде или в тексте есть имя 'Лидия Лиханская' — ответьте ровно `Нет`.  
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
                    "Важно: возвращай только ОДНУ саму ссылку, без дополнительного текста и форматирования! Если контактов нет - ответь 'нет'. @keys_manager - НЕ подходит"
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


def safe_process_text_with_gpt(text: str, force: bool = False) -> str:
    """
    Обработка текста через Yandex GPT.
    - force=True: всегда вызывает GPT (для фото+текст объявлений)
    - force=False: пустой текст не отправляется
    """
    text = (text or "").strip()
    if not text and not force:
        logger.warning("⚠️ GPT: Пустой текст без force=True, пропуск обработки")
        return ""
    try:
        sdk = YCloudML(folder_id=os.getenv("FOLDER_ID"), auth=os.getenv("AUTH"))
        messages_1 = [
            {"role": "system", "text": "Переформулируй объявление: комнаты, цена, адрес, условия, описание. Добавь эмодзи."},
            {"role": "user", "text": text or "Объявление с фото"},
        ]
        result = sdk.models.completions("yandexgpt").configure(temperature=0.5).run(messages_1)
        result_text = (result.text or "").strip()
        if not result_text:
            logger.warning("⚠️ GPT вернул пустой текст, подставляю заглушку")
            return "Объявление с фото"
        logger.info(f"✅ GPT обработал текст. Длина: {len(result_text)}")
        return result_text
    except Exception as e:
        logger.error(f"❌ GPT ошибка обработки текста: {e}", exc_info=True)
        return "Объявление с фото"
