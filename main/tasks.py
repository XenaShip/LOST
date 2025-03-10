import requests
import json
import os
from celery import shared_task
from django.conf import settings
from .models import MESSAGE
from telegram import Bot, InputMediaPhoto

# Получаем переменные окружения
YANDEX_GPT_API_KEY = os.getenv("YANDEX_GPT_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID")


@shared_task
def process_and_send_messages():
    """Фоновая задача Celery: берет сообщения из БД, переделывает с Yandex GPT и отправляет в Telegram."""

    messages = MESSAGE.objects.filter(sent=False)  # Выбираем только неотправленные

    if not messages.exists():
        return "Нет сообщений для обработки."

    bot = Bot(token=TELEGRAM_BOT_TOKEN)

    for message in messages:
        try:
            # Просим Yandex GPT переделать текст по шаблону
            formatted_text = rewrite_text_with_yandex_gpt(message.text)

            # Проверяем, все ли нужные поля извлечены
            if "Количество комнат:" not in formatted_text or "Контакты:" not in formatted_text:
                message.sent = True  # Если формат не совпадает, просто помечаем как обработанное
                message.save()
                continue

            # Формируем текст сообщения
            message_text = f"🏠 *Новое объявление!*\n\n{formatted_text}"

            # Отправляем изображения, если есть
            if message.images:
                images = json.loads(message.images) if isinstance(message.images, str) else message.images
                if images:
                    media_group = [InputMediaPhoto(media=image_url) for image_url in images]
                    bot.send_media_group(chat_id=TELEGRAM_CHANNEL_ID, media=media_group)

            # Отправляем текстовое сообщение
            bot.send_message(chat_id=TELEGRAM_CHANNEL_ID, text=message_text, parse_mode="Markdown")

            # Отмечаем сообщение как отправленное
            message.sent = True
            message.save()

        except Exception as e:
            print(f"Ошибка при обработке сообщения {message.id}: {e}")

    return "Все сообщения обработаны."


def rewrite_text_with_yandex_gpt(text):
    """Функция отправляет текст в Yandex GPT и получает структурированный ответ."""

    url = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
    headers = {
        "Authorization": f"Api-Key {YANDEX_GPT_API_KEY}",
        "Content-Type": "application/json"
    }

    prompt = (
        f"Извлеки информацию из текста в следующем формате:\n"
        f"- Количество комнат: [извлеченное значение]\n"
        f"- Местонахождение: [извлеченное значение]\n"
        f"- Цена: [извлеченное значение]\n"
        f"- Условия: [извлеченное значение]\n"
        f"- Контакты: [извлеченное значение]\n\n"
        f"Текст объявления: {text}"
    )

    data = {
        "modelUri": "gpt://b1gbmcevaimcqghhpuu7/yandexgpt-lite",
        "completionOptions": {"stream": False, "temperature": 0.7, "maxTokens": 200},
        "messages": [{"role": "user", "text": prompt}]
    }

    response = requests.post(url, json=data, headers=headers)

    if response.status_code == 200:
        result = response.json()
        return result['result']['alternatives'][0]['message']['text']
    else:
        raise Exception(f"Ошибка Yandex GPT: {response.status_code}, {response.text}")
