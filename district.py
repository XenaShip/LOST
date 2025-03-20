import os

import requests
from dotenv import load_dotenv

load_dotenv()
YANDEX_API_KEY = os.getenv("YANDEX_GEOCODER_API_KEY")  # 🔑 Вставь свой API-ключ

# 🔍 Границы округов Москвы (приблизительно)
DISTRICTS = {
    "ЦАО": [(55.715, 37.565), (55.785, 37.675)],
    "САО": [(55.825, 37.455), (55.905, 37.625)],
    "ЮАО": [(55.570, 37.580), (55.660, 37.730)],
    "ЗАО": [(55.645, 37.350), (55.750, 37.520)],
    "ВАО": [(55.720, 37.720), (55.830, 37.900)],
}

def get_district_by_coords(lat, lon):
    """Определяем округ Москвы по координатам"""
    for district, ((lat_min, lon_min), (lat_max, lon_max)) in DISTRICTS.items():
        if lat_min <= lat <= lat_max and lon_min <= lon <= lon_max:
            return district
    return "другой"

# 🔍 Получаем координаты адреса через Яндекс API
def get_coords_by_address(address):
    url = f"https://geocode-maps.yandex.ru/1.x/?apikey={YANDEX_API_KEY}&geocode={address}&format=json"
    try:
        response = requests.get(url).json()
        pos = response["response"]["GeoObjectCollection"]["featureMember"][0]["GeoObject"]["Point"]["pos"]
        lon, lat = map(float, pos.split())  # Переставляем местами
        return lat, lon
    except Exception as e:
        print(f"❌ Ошибка получения координат: {e}")
        return None

# 🔍 Вводим адрес и находим округ
address = input("Введите адрес: ")
coords = get_coords_by_address(address)

if coords:
    district = get_district_by_coords(*coords)
    print(f"🎯 Район: {district}")
else:
    print("❌ Не удалось найти район.")
