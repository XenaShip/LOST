import os
import django
import requests
import json
from django.core.management.base import BaseCommand
from dotenv import load_dotenv
from telegram import Bot, InputMediaPhoto
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes

load_dotenv()
# Настройка Django перед импортом моделей
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")  # Укажите имя вашего проекта
django.setup()

from main.models import MESSAGE  # Импорт модели после настройки Django

# Функция для работы с Yandex GPT
def rewrite_text_with_yandex_gpt(text, api_key):
    url = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
    headers = {
        "Authorization": f"Api-Key {api_key}",
        "Content-Type": "application/json"
    }
    prompt = (
        f"Извлеки из текста информацию о количестве комнат, местонахождении, цене, условиях и контактах.\n"
        f"Верни ответ в формате:\n"
        f"- Количество комнат: [извлеченное значение]\n"
        f"- Местонахождение: [извлеченное значение]\n"
        f"- Цена: [извлеченное значение]\n"
        f"- Условия: [извлеченное значение]\n"
        f"- Контакты: [извлеченное значение]\n\n"
        f"Текст: {text}"
    )
    data = {
        "modelUri": "gpt://b1gbmcevaimcqghhpuu7/yandexgpt-lite",  # Замените на ваш Folder ID и имя модели
        "completionOptions": {
            "stream": False,
            "temperature": 0.7,
            "maxTokens": 200
        },
        "messages": [
            {"role": "user", "text": prompt}
        ]
    }
    response = requests.post(url, json=data, headers=headers)
    if response.status_code == 200:
        result = response.json()
        if 'result' in result and 'alternatives' in result['result']:
            return result['result']['alternatives'][0]['message']['text']
        else:
            raise Exception(f"Ошибка Yandex GPT: ответ не содержит ожидаемых данных: {result}")
    else:
        raise Exception(f"Ошибка Yandex GPT: {response.status_code}, {response.text}")

# Функция для отправки сообщений в Telegram
def send_to_telegram_channel(message_text, images, bot_token, channel_id):
    bot = Bot(token=bot_token)
    if images:
        try:
            # Если images — это JSON-строка, преобразуем её в список
            if isinstance(images, str):
                images = json.loads(images)
            if isinstance(images, list) and images:
                media_group = [InputMediaPhoto(media=image_url) for image_url in images]
                bot.send_media_group(chat_id=channel_id, media=media_group)
        except json.JSONDecodeError:
            print("Ошибка: Невозможно разобрать JSON с изображениями.")
    bot.send_message(chat_id=channel_id, text=message_text, parse_mode="Markdown")

# Django команда для запуска бота
class Command(BaseCommand):
    help = "Бот для отправки сообщений в Telegram-канал"

    def handle(self, *args, **kwargs):
        self.stdout.write("Команда запущена")  # Проверим, что команда вообще запускается

        # Используем переменные окружения
        YANDEX_GPT_API_KEY = os.getenv("YANDEX_GPT_API_KEY")
        TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
        TELEGRAM_CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID")

        self.stdout.write(f"API-ключ: {YANDEX_GPT_API_KEY}")  # Проверим, загружаются ли переменные
        self.stdout.write(f"Бот-токен: {TELEGRAM_BOT_TOKEN}")
        self.stdout.write(f"Канал: {TELEGRAM_CHANNEL_ID}")

        if not all([YANDEX_GPT_API_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_CHANNEL_ID]):
            self.stdout.write(self.style.ERROR("Не заданы все переменные окружения!"))
            return

        self.stdout.write("Получаем сообщения из базы...")
        messages = MESSAGE.objects.filter(sent=False)

        if not messages.exists():
            self.stdout.write("Нет сообщений для обработки. Завершение работы.")
            return

        for message in messages:
            self.stdout.write(f"Обрабатываем сообщение {message.id}...")

            try:
                formatted_text = rewrite_text_with_yandex_gpt(message.text, YANDEX_GPT_API_KEY)

                if "Количество комнат:" not in formatted_text or "Контакты:" not in formatted_text:
                    message.sent = True
                    message.save()
                    self.stdout.write(f"Сообщение {message.id} пропущено (не соответствует формату).")
                    continue

                message_text = f"🏠 *Новое объявление!*\n\n{formatted_text}"
                send_to_telegram_channel(message_text, message.images, TELEGRAM_BOT_TOKEN, TELEGRAM_CHANNEL_ID)

                message.sent = True
                message.save()
                self.stdout.write(self.style.SUCCESS(f"Сообщение {message.id} отправлено!"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Ошибка при обработке сообщения {message.id}: {e}"))