from django.template.loader import render_to_string
from django.conf import settings
import requests


def send_notification_to_user(user_id, message_instance):
    info = message_instance.info_set.first()

    # Формируем текст сообщения
    text = render_to_string('notification.txt', {
        'ad': message_instance,
        'info': info
    })

    # Отправляем текст
    send_telegram_message(user_id, text)

    # Отправляем фото, если они есть
    if hasattr(message_instance, 'images') and message_instance.images:
        for image_url in message_instance.images[:5]:  # Не более 5 фото
            send_telegram_photo(user_id, image_url)


def send_telegram_message(user_id, text):
    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        'chat_id': user_id,
        'text': text,
        'parse_mode': 'HTML'
    }
    requests.post(url, json=payload)


def send_telegram_photo(user_id, photo_url, caption=""):
    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendPhoto"
    payload = {
        'chat_id': user_id,
        'photo': photo_url,
        'caption': caption,
        'parse_mode': 'HTML'
    }
    requests.post(url, json=payload)