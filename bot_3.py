import asyncio
import json
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, message
from asgiref.sync import sync_to_async
import os
import django
from dotenv import load_dotenv
from aiogram import types
from aiogram.filters.state import StateFilter
from packaging.version import CmpKey

# Настройки Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from main.models import MESSAGE, INFO, CLIENT_INFO

load_dotenv()
TOKEN = os.getenv("TOKEN3")

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)
dp = Dispatcher()

# Определяем состояния для FSM
class RentForm(StatesGroup):
    price = State()
    rooms = State()
    metro_distance = State()
    district = State()
    area = State()

class ClientForm(StatesGroup):
    price = State()
    rooms = State()
    metro_distance = State()
    district = State()
    area = State()
    address = State()
    phone = State()
    telegram = State()
    images = State()

# Кнопки "Не важно"
def any_button(callback_data):
    return InlineKeyboardButton(text="Не важно", callback_data=callback_data)

# Стартовое сообщение
@dp.message(CommandStart())
async def start(message: types.Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Снять квартиру", callback_data="rent")],
        [InlineKeyboardButton(text="Сдать квартиру", callback_data="client")]
    ])
    await message.answer("Вы хотите снять или сдать квартиру?", reply_markup=keyboard)

# Выбор "Снять" или "Сдать"
# В обработчике start_rent (для снятия квартиры) обновляем клавиатуру с ценами:
@dp.callback_query(F.data == "rent")
async def start_rent(callback: types.CallbackQuery, state: FSMContext):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="30 000 ₽", callback_data="price_30000")],
        [InlineKeyboardButton(text="50 000 ₽", callback_data="price_50000")],
        [InlineKeyboardButton(text="70 000 ₽", callback_data="price_70000")],
        [InlineKeyboardButton(text="100 000+ ₽", callback_data="price_100000")],
        [any_button("price_any")]
    ])
    await callback.message.answer("Выберите минимальную цену:", reply_markup=keyboard)
    await state.set_state(RentForm.price)



@dp.callback_query(F.data == "client")
async def process_client_start(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Введите цену сдачи квартиры (только число, без пробелов и знаков).")
    await state.set_state(ClientForm.price)

@dp.message(ClientForm.price)
async def process_client_price(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("⚠️ Введите цену числом, без пробелов и знаков. Например: 50000")
        return
    await state.update_data(price=int(message.text))

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1 комната", callback_data="client_rooms_1")],
        [InlineKeyboardButton(text="2 комнаты", callback_data="client_rooms_2")],
        [InlineKeyboardButton(text="3+ комнаты", callback_data="client_rooms_3")]
    ])
    await message.answer("Выберите количество комнат:", reply_markup=keyboard)
    await state.set_state(ClientForm.rooms)

@dp.callback_query(F.data.startswith("client_rooms_"))
async def process_client_rooms(callback: types.CallbackQuery, state: FSMContext):
    rooms = int(callback.data.split("_")[2])
    await state.update_data(rooms=rooms)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="До 500 м", callback_data="client_metro_500")],
        [InlineKeyboardButton(text="До 1000 м", callback_data="client_metro_1000")],
        [InlineKeyboardButton(text="До 2000 м", callback_data="client_metro_2000")],
        [InlineKeyboardButton(text="2000 м+", callback_data="client_metro_2000+")]
    ])
    await callback.message.answer("Выберите расстояние до метро:", reply_markup=keyboard)
    await state.set_state(ClientForm.metro_distance)

@dp.callback_query(F.data.startswith("client_metro_"))
async def process_client_metro(callback: types.CallbackQuery, state: FSMContext):
    if callback.data == "client_metro_2000+":
        metro_distance = 2001  # Специальное значение для "2000 м+"
    else:
        metro_distance = int(callback.data.split("_")[2])
    await state.update_data(count_meters_metro=metro_distance)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="ЦАО", callback_data="client_district_CAO")],
        [InlineKeyboardButton(text="ЮАО", callback_data="client_district_YUAO")],
        [InlineKeyboardButton(text="САО", callback_data="client_district_SAO")],
        [InlineKeyboardButton(text="ЗАО", callback_data="client_district_ZAO")],
        [InlineKeyboardButton(text="ВАО", callback_data="client_district_VAO")]
    ])
    await callback.message.answer("Выберите район:", reply_markup=keyboard)
    await state.set_state(ClientForm.district)

@dp.callback_query(F.data.startswith("client_district_"))
async def process_client_district(callback: types.CallbackQuery, state: FSMContext):
    district = callback.data.split("_")[2]
    await state.update_data(location=district)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="До 30 м²", callback_data="client_area_30")],
        [InlineKeyboardButton(text="До 50 м²", callback_data="client_area_50")],
        [InlineKeyboardButton(text="До 70 м²", callback_data="client_area_70")],
        [InlineKeyboardButton(text="70 м²+", callback_data="client_area_70+")]
    ])
    await callback.message.answer("Выберите площадь квартиры:", reply_markup=keyboard)
    await state.set_state(ClientForm.area)

@dp.callback_query(F.data.startswith("client_area_"))
async def process_client_area(callback: types.CallbackQuery, state: FSMContext):
    area = 70 if callback.data == "client_area_70+" else int(callback.data.split("_")[2])
    await state.update_data(count_meters_flat=area)

    await callback.message.answer("Введите адрес квартиры:")
    await state.set_state(ClientForm.address)

@dp.message(ClientForm.address)
async def process_client_address(message: types.Message, state: FSMContext):
    await state.update_data(adress=message.text)

    await message.answer("Введите номер телефона:")
    await state.set_state(ClientForm.phone)

@dp.message(ClientForm.phone)
async def process_client_phone(message: types.Message, state: FSMContext):
    await state.update_data(phone_number=message.text)

    await message.answer("Введите ваш Telegram (пример: @username):")
    await state.set_state(ClientForm.telegram)


@dp.message(ClientForm.telegram)
async def process_tg(message: types.Message, state: FSMContext):
    await state.update_data(tg=message.text)
    await message.answer("Отправьте фото квартиры (можно несколько):")
    await state.set_state(ClientForm.images)


@dp.message(ClientForm.images, F.content_type == 'photo')
async def process_images(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    images = user_data.get("images", [])

    # Сохраняем file_id самого большого доступного размера фото
    photo_id = message.photo[-1].file_id
    images.append(photo_id)
    await state.update_data(images=images)

    await message.answer("Фото добавлено. Отправьте ещё или напишите 'Готово' для завершения.")


@dp.message(ClientForm.images)
async def finish_images(message: types.Message, state: FSMContext):
    if message.text and message.text.lower() == "готово":
        user_data = await state.get_data()
        images = user_data.get("images", [])

        # Проверяем, есть ли хотя бы одно фото
        if not images:
            await message.answer("Пожалуйста, отправьте хотя бы одно фото квартиры.")
            return

        try:
            await sync_to_async(CLIENT_INFO.objects.create)(
                price=user_data["price"],
                rooms=user_data["rooms"],
                count_meters_flat=user_data["count_meters_flat"],
                count_meters_metro=user_data["count_meters_metro"],
                location=user_data["location"],
                adress=user_data["adress"],
                phone_number=user_data["phone_number"],
                tg=user_data["tg"],
                images=images  # Уже список file_id, не нужно json.dumps
            )
            await message.answer("Ваше объявление сохранено!")
            await state.clear()
        except Exception as e:
            logging.error(f"Ошибка при сохранении объявления: {e}")
            await message.answer("Произошла ошибка при сохранении объявления. Пожалуйста, попробуйте позже.")
    else:
        await message.answer("Отправьте фото или напишите 'Готово', чтобы закончить.")


# Обработчики для "Снять квартиру" (RentForm)
@dp.callback_query(F.data.startswith("price_"))
async def process_price(callback: types.CallbackQuery, state: FSMContext):
    if callback.data == "price_any":
        price = None
    elif callback.data == "price_100000":
        price = 100000  # Для варианта "100 000+"
    else:
        price = int(callback.data.split("_")[1])
    await state.update_data(price=price)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1 комната", callback_data="rooms_1")],
        [InlineKeyboardButton(text="2 комнаты", callback_data="rooms_2")],
        [InlineKeyboardButton(text="3 комнаты", callback_data="rooms_3")],
        [InlineKeyboardButton(text="4+ комнаты", callback_data="rooms_4")],
        [any_button("rooms_any")]
    ])
    await callback.message.answer("Выберите количество комнат:", reply_markup=keyboard)
    await state.set_state(RentForm.rooms)

@dp.callback_query(F.data.startswith("rooms_"))
async def process_rooms(callback: types.CallbackQuery, state: FSMContext):
    rooms = None if callback.data == "rooms_any" else int(callback.data.split("_")[1])
    await state.update_data(rooms=rooms)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="ЦАО", callback_data="district_CAO")],
        [InlineKeyboardButton(text="ЮАО", callback_data="district_YUAO")],
        [InlineKeyboardButton(text="САО", callback_data="district_SAO")],
        [InlineKeyboardButton(text="ЗАО", callback_data="district_ZAO")],
        [InlineKeyboardButton(text="ВАО", callback_data="district_VAO")],
        [any_button("district_any")]
    ])
    await callback.message.answer("Выберите район:", reply_markup=keyboard)
    await state.set_state(RentForm.district)

@dp.callback_query(F.data.startswith("metro_"))
async def process_metro(callback: types.CallbackQuery, state: FSMContext):
    if callback.data == "metro_any":
        metro_distance = None
    elif callback.data == "metro_2000+":
        metro_distance = 2001  # Специальное значение для "2000 м+"
    else:
        metro_distance = int(callback.data.split("_")[1])
    await state.update_data(metro_distance=metro_distance)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="До 500 м", callback_data="metro_500")],
        [InlineKeyboardButton(text="До 1000 м", callback_data="metro_1000")],
        [InlineKeyboardButton(text="До 2000 м", callback_data="metro_2000")],
        [InlineKeyboardButton(text="2000 м+", callback_data="metro_2000+")],
        [any_button("metro_any")]
    ])
    await callback.message.answer("Выберите район:", reply_markup=keyboard)
    await state.set_state(RentForm.district)

@dp.callback_query(F.data.startswith("district_"))
async def process_district(callback: types.CallbackQuery, state: FSMContext):
    district = None if callback.data == "district_any" else callback.data.split("_")[1]
    await state.update_data(district=district)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="До 30 м²", callback_data="area_30")],
        [InlineKeyboardButton(text="До 50 м²", callback_data="area_50")],
        [InlineKeyboardButton(text="До 70 м²", callback_data="area_70")],
        [InlineKeyboardButton(text="70 м²+", callback_data="area_70+")],
        [any_button("area_any")]
    ])
    await callback.message.answer("Выберите площадь:", reply_markup=keyboard)
    await state.set_state(RentForm.area)

@dp.callback_query(F.data.startswith("area_"))
async def process_area(callback: types.CallbackQuery, state: FSMContext):
    """Обрабатывает выбор площади и отправляет объявления с фото и текстом."""

    # Получаем значение площади из callback_data
    area = None if callback.data == "area_any" else int(callback.data.split("_")[1])
    await state.update_data(area=area)

    # Получаем все данные пользователя
    user_data = await state.get_data()
    await state.clear()

    # Фильтруем объявления
    results = await sync_to_async(filter_ads)(user_data)

    if results:
        for info in results:
            msg = info.message  # Получаем связанный MESSAGE

            text = f"🏠 {msg.new_text or msg.text}\n📍 Адрес: {info.adress}\n💰 Цена: {info.price}₽"

            # Проверяем изображения
            if msg.images:
                try:
                    images = json.loads(msg.images) if isinstance(msg.images, str) else msg.images  # Декодируем JSON
                    media = [types.InputMediaPhoto(media=img) for img in images[1:] if img]

                    if media:
                        await callback.message.answer_media_group(media)  # Отправляем группу фото
                except Exception as e:
                    print(f"Ошибка загрузки изображений: {e}")

            # Отправляем текст объявления
            await callback.message.answer(text)

    else:
        await callback.message.answer("😔 Не найдено объявлений по вашим параметрам.")


# Фильтрация объявлений
def filter_ads(filters):
    query = INFO.objects.select_related("message")

    # Фильтр по цене
    if filters.get("price") is not None:
        if filters["price"] == 100000:  # Для варианта "100 000+"
            query = query.filter(price__gte=100000)
        else:
            query = query.filter(price__gte=filters["price"])

    # Фильтр по расстоянию до метро
    if filters.get("metro_distance") is not None:
        if filters["metro_distance"] == 2001:  # Для варианта "2000 м+"
            query = query.filter(count_meters_metro__gt=2000)
        else:
            query = query.filter(count_meters_metro__lte=filters["metro_distance"])

    # Остальные фильтры без изменений
    if filters.get("rooms") is not None:
        if filters["rooms"] == 4:
            query = query.filter(rooms__gte=4)
        else:
            query = query.filter(rooms=filters["rooms"])

    if filters.get("district") is not None:
        query = query.filter(location=filters["district"])

    if filters.get("area") is not None:
        if filters["area"] == 70:
            query = query.filter(count_meters_flat__gte=70)
        else:
            query = query.filter(count_meters_flat__lte=filters["area"])

    return list(query)

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
