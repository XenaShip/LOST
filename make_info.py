import os
import time

from dotenv import load_dotenv
from selenium.webdriver.support.expected_conditions import text_to_be_present_in_element
from yandex_cloud_ml_sdk import YCloudML

load_dotenv()

def process_text_with_gpt_rooms(text):
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
            "text": "Извлеки из текста кол-во комнат. Ответ напиши только цифры",
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


def process_text_with_gpt_price(text):
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
            "text": "Извлеки из текста цену. Ответ напиши только цифры",
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


def process_text_with_gpt_sq(text):
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
            "text": "Извлеки из текста площадь квартиры или комнаты. Ответ напиши только цифры. Если площадь не указана ответь нулем",
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


def process_text_with_gpt_adress(text):
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
            "text": "Извлеки из текста адрес",
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


