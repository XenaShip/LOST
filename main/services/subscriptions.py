from asgiref.sync import sync_to_async
from django.db.models import Q
from django.utils import timezone
from main.models import Subscription, INFO
from main.services.notifications import send_notification_to_user

DISTRICT_MAPPING = {
    'CAO': ['центр', 'цао', 'центральный'],
    'YUAO': ['юао', 'южный', 'юго-восточный'],
    'SAO': ['сао', 'северный', 'северо-западный'],
    'ZAO': ['зао', 'западный'],
    'VAO': ['вао', 'восточный']
}


def check_subscriptions_for_new_ad(message_instance):
    info = message_instance.info_set.first()
    if not info:
        return

    subscriptions = Subscription.objects.filter(is_active=True)

    for sub in subscriptions:
        # Проверка цены
        price_ok = ((sub.min_price is None or (info.price and info.price >= sub.min_price)) and (sub.max_price is None or (info.price and info.price <= sub.max_price)))
        rooms_ok = ((sub.min_rooms is None or (info.rooms and info.rooms >= sub.min_rooms)) and(sub.max_rooms is None or (info.rooms and info.rooms <= sub.max_rooms)))
        district_ok = True
        if sub.district != 'ANY' and info.location:
            district_keywords = DISTRICT_MAPPING.get(sub.district, [])
        district_ok = any(
            keyword in info.location.lower()
            for keyword in district_keywords
        )

        # Проверка расстояния до метро (конвертация минут в метры)
        metro_ok = True
        if sub.max_metro_distance and info.count_meters_metro:
        # Примерная конвертация: 1 мин пешком = 80 м
            meters = info.count_meters_metro * 80
        metro_ok = True
        if sub.max_metro_distance and info.count_meters_metro:
            meters = info.count_meters_metro * 80  # 1 мин пешком = ~80 м
            metro_ok = meters <= sub.max_metro_distance

        if price_ok and rooms_ok and district_ok and metro_ok:
            send_notification_to_user(sub.user_id, message_instance)


@sync_to_async
def async_create_or_update_subscription(user_id: int, username: str, params: dict):
    """Асинхронная версия для бота"""
    defaults = {
        'username': username,
        'is_active': True,
        'updated_at': timezone.now(),
        **params
    }
    Subscription.objects.update_or_create(
        user_id=user_id,
        defaults=defaults
    )