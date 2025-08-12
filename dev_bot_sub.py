import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, \
    InputMediaPhoto
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    CallbackContext,
    ConversationHandler,
    CallbackQueryHandler
)
from asgiref.sync import sync_to_async
import django

# Настройка Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from main.models import DEVSubscription

import re

MODERATION_CHANNEL_ID = int(os.getenv("MODERATION_CHANNEL_ID", "0"))  # ID закрытого канала для модерации
TERMS_MAX_LEN = int(os.getenv("TERMS_MAX_LEN", "180"))                # лимит символов для "Условия"
DESC_MAX_LEN  = int(os.getenv("DESC_MAX_LEN",  "800"))                # лимит символов для "Описание"

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Состояния диалога
PRICE, ROOMS, FLAT_AREA, DISTRICT, METRO_DISTANCE, CONFIRM = range(6)
(O_PRICE, O_ADDRESS, O_ROOMS, O_AREA, O_FLOOR, O_TERMS, O_DESC, O_CONTACTS, O_PHOTOS, O_PREVIEW) = range(100, 110)

# --- Клавиатуры ---
def get_price_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("До 35000₽", callback_data="price_0_35000")],
        [InlineKeyboardButton("35000-45000₽", callback_data="price_35000_45000")],
        [InlineKeyboardButton("45000-65000₽", callback_data="price_45000_65000")],
        [InlineKeyboardButton("65000-100000₽", callback_data="price_65000_100000")],
        [InlineKeyboardButton("Более 100000₽", callback_data="price_100000_999999999")],
        [InlineKeyboardButton("Не важно", callback_data="price_any")],
    ])


def get_rooms_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Студия", callback_data="rooms_0_0")],
        [InlineKeyboardButton("1 комната", callback_data="rooms_1_1")],
        [InlineKeyboardButton("2 комнаты", callback_data="rooms_2_2")],
        [InlineKeyboardButton("3 комнаты", callback_data="rooms_3_3")],
        [InlineKeyboardButton("4+ комнат", callback_data="rooms_4_10")],
        [InlineKeyboardButton("Не важно", callback_data="rooms_any")],
    ])


def get_area_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("До 30 м²", callback_data="area_0_30")],
        [InlineKeyboardButton("30-50 м²", callback_data="area_30_50")],
        [InlineKeyboardButton("50-70 м²", callback_data="area_50_70")],
        [InlineKeyboardButton("70-90 м²", callback_data="area_70_90")],
        [InlineKeyboardButton("Более 90 м²", callback_data="area_90_999")],
        [InlineKeyboardButton("Не важно", callback_data="area_any")],
    ])


def get_district_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("ЦАО", callback_data="district_CAO")],
        [InlineKeyboardButton("ЮАО", callback_data="district_YUAO")],
        [InlineKeyboardButton("САО", callback_data="district_SAO")],
        [InlineKeyboardButton("ЗАО", callback_data="district_ZAO")],
        [InlineKeyboardButton("ВАО", callback_data="district_VAO")],
        [InlineKeyboardButton("Не важно", callback_data="district_ANY")],
    ])


def get_metro_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Близко", callback_data="metro_close")],
        [InlineKeyboardButton("🚫 Не важно",        callback_data="metro_any")],
    ])


def get_confirm_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Подтвердить", callback_data="confirm_yes"),
            InlineKeyboardButton("❌ Отменить", callback_data="confirm_no")
        ],
    ])


def get_main_keyboard():
    keyboard = [
        [KeyboardButton("▶️ Старт")],
        [KeyboardButton("📬 Подписаться")],
        [KeyboardButton("ℹ️ Моя подписка")],
        [KeyboardButton("📝 Предложить своё")],
        [KeyboardButton("❌ Отписка")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def get_offer_rooms_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Студия",  callback_data="offer_rooms_studio"),
         InlineKeyboardButton("Комната", callback_data="offer_rooms_room")],
        [InlineKeyboardButton("1", callback_data="offer_rooms_1"),
         InlineKeyboardButton("2", callback_data="offer_rooms_2"),
         InlineKeyboardButton("3", callback_data="offer_rooms_3"),
         InlineKeyboardButton("4+", callback_data="offer_rooms_4plus")],
    ])

def get_offer_photos_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Готово", callback_data="offer_photos_done")],
        [InlineKeyboardButton("⏭ Пропустить", callback_data="offer_photos_skip")],
    ])

def _digits(text: str) -> str:
    return re.sub(r"[^\d]", "", text or "")

def _is_valid_contact(s: str) -> bool:
    s = (s or "").strip()
    if s.startswith("tg://user?id="):
        return True
    if s.startswith("@") and len(s) >= 5:
        return True
    if "t.me/" in s or s.startswith("https://t.me/") or s.startswith("http://t.me/"):
        return True
    if re.fullmatch(r"\+?\d[\d \-]{7,}", s):
        return True
    return False

def build_offer_text(d: dict) -> str:
    # Плоский текст без Markdown — в канале модерации будет читабельно и безопасно
    parts = []
    parts.append(f"💰 Цена: {d['price']} ₽")
    parts.append(f"📍 Адрес: {d['address']}")
    parts.append(f"🏠 Комнаты: {d['rooms']}")
    parts.append(f"📐 Площадь: {d['area']} м²")
    parts.append(f"🏢 Этаж: {d['floor']}")
    parts.append(f"⚙️ Условия: {d['terms']}")
    parts.append(f"📝 Описание: {d['desc']}")
    parts.append(f"🔗 Контакты: {d['contacts']}")
    author = d.get('author', '')
    if author:
        parts.append(f"👤 Автор: {author}")
    return "\n".join(parts)

async def offer_start(update: Update, context: CallbackContext) -> int:
    context.user_data.clear()
    await update.message.reply_text(
        "Укажите цену (числом, без текста, например: 65000):",
        reply_markup=get_main_keyboard()
    )
    return O_PRICE

async def offer_price(update: Update, context: CallbackContext) -> int:
    val = _digits(update.message.text)
    if not val:
        await update.message.reply_text("Не получилось распознать число. Введите цену, например: 65000")
        return O_PRICE
    context.user_data['price'] = int(val)
    await update.message.reply_text("Укажите адрес (улица, дом, район и т.п.):")
    return O_ADDRESS

async def offer_address(update: Update, context: CallbackContext) -> int:
    text = (update.message.text or "").strip()
    if len(text) < 5:
        await update.message.reply_text("Слишком короткий адрес. Уточните, пожалуйста.")
        return O_ADDRESS
    context.user_data['address'] = text
    await update.message.reply_text("Выберите тип/кол-во комнат:", reply_markup=get_offer_rooms_keyboard())
    return O_ROOMS

async def offer_rooms_cb(update: Update, context: CallbackContext) -> int:
    q = update.callback_query
    await q.answer()
    data = q.data  # offer_rooms_...
    mapping = {
        "offer_rooms_studio": "Студия",
        "offer_rooms_room":   "Комната",
        "offer_rooms_1":      "1",
        "offer_rooms_2":      "2",
        "offer_rooms_3":      "3",
        "offer_rooms_4plus":  "4+",
    }
    context.user_data['rooms'] = mapping.get(data, "—")
    await q.edit_message_text("Укажите площадь (м²), например: 42")
    return O_AREA

async def offer_area(update: Update, context: CallbackContext) -> int:
    val = _digits(update.message.text)
    if not val:
        await update.message.reply_text("Введите число, например: 42")
        return O_AREA
    context.user_data['area'] = int(val)
    await update.message.reply_text("Укажите этаж (например: 5 или 5 из 17):")
    return O_FLOOR

async def offer_floor(update: Update, context: CallbackContext) -> int:
    text = (update.message.text or "").strip()
    if not text:
        await update.message.reply_text("Введите этаж, например: 5 или 5 из 17")
        return O_FLOOR
    context.user_data['floor'] = text
    await update.message.reply_text(f"Напишите условия (не более {TERMS_MAX_LEN} символов):")
    return O_TERMS

async def offer_terms(update: Update, context: CallbackContext) -> int:
    text = (update.message.text or "").strip()
    if len(text) > TERMS_MAX_LEN:
        await update.message.reply_text(f"Слишком длинно. Сократите до {TERMS_MAX_LEN} символов.")
        return O_TERMS
    context.user_data['terms'] = text or "—"
    await update.message.reply_text(f"Опишите квартиру (не более {DESC_MAX_LEN} символов):")
    return O_DESC

async def offer_desc(update: Update, context: CallbackContext) -> int:
    text = (update.message.text or "").strip()
    if len(text) > DESC_MAX_LEN:
        await update.message.reply_text(f"Слишком длинно. Сократите до {DESC_MAX_LEN} символов.")
        return O_DESC
    context.user_data['desc'] = text or "—"
    await update.message.reply_text("Укажите ваши контакты (ссылка на тг, @username, tg://user?id=..., или номер телефона):")
    return O_CONTACTS

async def offer_contacts(update: Update, context: CallbackContext) -> int:
    text = (update.message.text or "").strip()
    if not _is_valid_contact(text):
        await update.message.reply_text("Не похоже на контакт. Пример: @username или https://t.me/username или +79991234567")
        return O_CONTACTS
    context.user_data['contacts'] = text

    user = update.effective_user
    context.user_data['author'] = f"@{user.username}" if user and user.username else f"id:{user.id if user else '-'}"

    # подготовим корзину для фото
    context.user_data['photos'] = []

    await update.message.reply_text(
        "Прикрепите до 10 фотографий (можно альбомом или по одной). "
        "Когда закончите — нажмите «Готово», либо «Пропустить».",
        reply_markup=get_offer_photos_keyboard()
    )
    return O_PHOTOS


async def offer_photos(update: Update, context: CallbackContext) -> int:
    photos = context.user_data.get('photos', [])
    if not update.message.photo:
        await update.message.reply_text("Пришлите фото как изображение. Когда закончите — нажмите «Готово».",
                                        reply_markup=get_offer_photos_keyboard())
        return O_PHOTOS

    if len(photos) >= 10:
        await update.message.reply_text("Уже 10 фото, больше нельзя. Нажмите «Готово» или «Пропустить».",
                                        reply_markup=get_offer_photos_keyboard())
        return O_PHOTOS

    # берём самое большое превью как file_id
    file_id = update.message.photo[-1].file_id
    photos.append(file_id)
    context.user_data['photos'] = photos

    await update.message.reply_text(
        f"Добавлено фото {len(photos)}/10. Можете отправить ещё или нажмите «Готово».",
        reply_markup=get_offer_photos_keyboard()
    )
    return O_PHOTOS


async def offer_photos_done(update: Update, context: CallbackContext) -> int:
    q = update.callback_query
    await q.answer()
    preview = build_offer_text(context.user_data) + f"\n🖼 Фото: {len(context.user_data.get('photos', []))} шт."
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Опубликовать", callback_data="offer_publish"),
        InlineKeyboardButton("❌ Отменить", callback_data="offer_cancel"),
    ]])
    await q.edit_message_text("Проверьте, пожалуйста, данные:\n\n" + preview, reply_markup=kb)
    return O_PREVIEW

async def offer_photos_skip(update: Update, context: CallbackContext) -> int:
    q = update.callback_query
    await q.answer()
    context.user_data['photos'] = []
    return await offer_photos_done(update, context)

async def offer_publish(update: Update, context: CallbackContext) -> int:
    q = update.callback_query
    await q.answer()
    text = build_offer_text(context.user_data)

    if not MODERATION_CHANNEL_ID:
        await q.edit_message_text("Ошибка: не задан MODERATION_CHANNEL_ID в .env. Укажи ID закрытого канала.")
        context.user_data.clear()
        return ConversationHandler.END

    try:
        # 1) текст
        await context.bot.send_message(chat_id=MODERATION_CHANNEL_ID, text="🆕 Новое предложение на модерацию:\n\n" + text)
        # 2) фото (если есть)
        photos = context.user_data.get('photos', [])[:10]
        if photos:
            media = [InputMediaPhoto(media=pid) for pid in photos]
            await context.bot.send_media_group(chat_id=MODERATION_CHANNEL_ID, media=media)

    except Exception as e:
        await q.edit_message_text(f"Не удалось отправить в канал модерации: {e}")
        context.user_data.clear()
        return ConversationHandler.END

    await q.edit_message_text("Спасибо за ваше предложение!\nМы опубликуем ваш пост после модерации.")
    context.user_data.clear()
    return ConversationHandler.END

async def offer_cancel_cb(update: Update, context: CallbackContext) -> int:
    q = update.callback_query
    await q.answer()
    await q.edit_message_text("Создание предложения отменено.")
    context.user_data.clear()
    return ConversationHandler.END

# --- Работа с БД ---
@sync_to_async
def get_subscription(user_id):
    try:
        return DEVSubscription.objects.get(user_id=user_id)
    except DEVSubscription.DoesNotExist:
        return None


@sync_to_async
def update_or_create_subscription(user_id, username, params):
    return DEVSubscription.objects.update_or_create(
        user_id=user_id,
        defaults={
            'username': username,
            'min_price': params.get('min_price'),
            'max_price': params.get('max_price'),
            'min_rooms': params.get('min_rooms'),
            'max_rooms': params.get('max_rooms'),
            'min_flat': params.get('min_flat'),
            'max_flat': params.get('max_flat'),
            'district': params.get('district', 'ANY'),
            'metro_close': params.get('metro_close', False),
            'is_active': True
        }
    )


@sync_to_async
def deactivate_subscription(user_id):
    try:
        sub = DEVSubscription.objects.get(user_id=user_id)
        sub.is_active = False
        sub.save()
        return True
    except DEVSubscription.DoesNotExist:
        return False


# --- Команды бота ---
async def start(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text(
        "🏡 Бот подписки на объявления о недвижимости\n\n"
        "Выберите действие:\n\n"
        "/subscribe - подписаться на обновления,\n\n"
        "/my_subscription - моя подписка,\n\n"
        "/unsubscribe - отписаться",
        reply_markup=get_main_keyboard()
    )


async def subscribe(update: Update, context: CallbackContext) -> int:
    context.user_data.clear()
    await update.message.reply_text(
        "💰 Выберите диапазон цен:",
        reply_markup=get_price_keyboard()  # Только inline-кнопки
    )
    return PRICE


async def process_price(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    await query.answer()

    data = query.data.split('_')
    if data[1] == 'any':
        context.user_data['min_price'] = None
        context.user_data['max_price'] = None
    else:
        context.user_data['min_price'] = int(data[1])
        context.user_data['max_price'] = int(data[2])

    await query.edit_message_text(
        "🚪 Выберите количество комнат:",
        reply_markup=get_rooms_keyboard()
    )
    return ROOMS


async def process_rooms(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    await query.answer()

    data = query.data.split('_')
    if data[1] == 'any':
        context.user_data['min_rooms'] = None
        context.user_data['max_rooms'] = None
    else:
        context.user_data['min_rooms'] = int(data[1])
        context.user_data['max_rooms'] = int(data[2])

    await query.edit_message_text(
        "📏 Выберите площадь квартиры:",
        reply_markup=get_area_keyboard()
    )
    return FLAT_AREA


async def process_area(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    await query.answer()

    data = query.data.split('_')
    if data[1] == 'any':
        context.user_data['min_flat'] = None
        context.user_data['max_flat'] = None
    else:
        context.user_data['min_flat'] = int(data[1])
        context.user_data['max_flat'] = int(data[2])

    await query.edit_message_text(
        "🗺️ Выберите округ:",
        reply_markup=get_district_keyboard()
    )
    return DISTRICT


async def process_district(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    await query.answer()

    data = query.data.split('_')
    context.user_data['district'] = data[1]

    await query.edit_message_text(
        "🚇 Выберите максимальное расстояние до метро:",
        reply_markup=get_metro_keyboard()
    )
    return METRO_DISTANCE


async def process_metro(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    await query.answer()

    # Сохраняем выбор пользователя
    if query.data == 'metro_close':
        context.user_data['metro_close'] = True
    else:  # 'metro_any'
        context.user_data['metro_close'] = False

    # Получаем человекочитаемое название округа
    district_name = dict(DEVSubscription.DISTRICT_CHOICES).get(
        context.user_data.get('district'),
        'Не важно'
    )

    # Формируем текст сводки
    summary = (
        "✅ Проверьте параметры подписки:\n\n"
        f"• Цена: {context.user_data.get('min_price', 'не важно')} - "
        f"{context.user_data.get('max_price', 'не важно')} ₽\n"
        f"• Комнат: {context.user_data.get('min_rooms', 'не важно')}-"
        f"{context.user_data.get('max_rooms', 'не важно')}\n"
        f"• Площадь: {context.user_data.get('min_flat', 'не важно')}-"
        f"{context.user_data.get('max_flat', 'не важно')} м²\n"
        f"• Округ: {district_name}\n"
        f"• До метро: {'Близко' if context.user_data['metro_close'] else '🚫 не важно'}\n\n"
        "Подтвердите ваш выбор:"
    )

    # Показываем сводку с кнопками подтверждения
    await query.edit_message_text(
        text=summary,
        reply_markup=get_confirm_keyboard()
    )
    return CONFIRM


async def process_confirmation(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    await query.answer()

    if query.data == 'confirm_yes':
        user = update.effective_user
        await update_or_create_subscription(
            user_id=user.id,
            username=user.username,
            params=context.user_data
        )
        await query.edit_message_text("🎉 Подписка успешно сохранена!")
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Вы можете продолжить работу с ботом:",
            reply_markup=get_main_keyboard()
        )
    else:
        await query.edit_message_text("Настройка подписки отменена.")
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Вы можете продолжить работу с ботом:",
            reply_markup=get_main_keyboard()
        )

    context.user_data.clear()
    return ConversationHandler.END


async def cancel(update: Update, context: CallbackContext) -> int:
    context.user_data.clear()
    await update.message.reply_text(
        "Настройка подписки отменена. Нажмите «Подписка», чтобы начать заново.",
        reply_markup=get_main_keyboard()
    )
    return ConversationHandler.END


async def my_subscription(update: Update, context: CallbackContext) -> None:
    sub = await get_subscription(update.effective_user.id)
    if sub:
        district_name = dict(DEVSubscription.DISTRICT_CHOICES).get(sub.district, 'Не важно')
        metro_text = 'Близко' if getattr(sub, 'metro_close', False) else 'не важно'

        text = (
            "📋 Ваша текущая подписка:\n\n"
            f"• Цена: {sub.min_price or 'не важно'} - {sub.max_price or 'не важно'} руб\n"
            f"• Комнат: {sub.min_rooms or 'не важно'}-{sub.max_rooms or 'не важно'}\n"
            f"• Площадь: {sub.min_flat or 'не важно'}-{sub.max_flat or 'не важно'} м²\n"
            f"• Округ: {district_name}\n"
             f"• До метро: {metro_text}\n\n"
            "Для изменения параметров нажмите «Подписка»"
        )
    else:
        text = "У вас нет активной подписки. Для создания нажмите «Подписка»"

    await update.message.reply_text(text, reply_markup=get_main_keyboard())


async def unsubscribe(update: Update, context: CallbackContext) -> None:
    if await deactivate_subscription(update.effective_user.id):
        await update.message.reply_text("✅ Вы успешно отписались от уведомлений", reply_markup=get_main_keyboard())
    else:
        await update.message.reply_text("❌ У вас нет активной подписки", reply_markup=get_main_keyboard())


def main() -> None:
    application = Application.builder().token(os.getenv("DEV_BOT_TOKEN_SUB")).build()

    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^📬 Подписаться$"), subscribe)],
        states={
            PRICE: [CallbackQueryHandler(process_price, pattern="^price_")],
            ROOMS: [CallbackQueryHandler(process_rooms, pattern="^rooms_")],
            FLAT_AREA: [CallbackQueryHandler(process_area, pattern="^area_")],
            DISTRICT: [CallbackQueryHandler(process_district, pattern="^district_")],
            METRO_DISTANCE: [CallbackQueryHandler(process_metro, pattern="^metro_")],
            CONFIRM: [CallbackQueryHandler(process_confirmation, pattern="^confirm_")],
        },
        fallbacks=[
            CommandHandler('cancel', cancel),
            MessageHandler(filters.Regex("^▶️ Старт$"), cancel),
            MessageHandler(filters.COMMAND, cancel),
        ],
    )
    offer_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^📝 Предложить своё$"), offer_start)],
        states={
            O_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, offer_price)],
            O_ADDRESS: [MessageHandler(filters.TEXT & ~filters.COMMAND, offer_address)],
            O_ROOMS: [CallbackQueryHandler(offer_rooms_cb, pattern="^offer_rooms_")],
            O_AREA: [MessageHandler(filters.TEXT & ~filters.COMMAND, offer_area)],
            O_FLOOR: [MessageHandler(filters.TEXT & ~filters.COMMAND, offer_floor)],
            O_TERMS: [MessageHandler(filters.TEXT & ~filters.COMMAND, offer_terms)],
            O_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, offer_desc)],
            O_CONTACTS: [MessageHandler(filters.TEXT & ~filters.COMMAND, offer_contacts)],

            # НОВОЕ: шаг с фотографиями
            O_PHOTOS: [
                MessageHandler(filters.PHOTO, offer_photos),
                CallbackQueryHandler(offer_photos_done, pattern="^offer_photos_done$"),
                CallbackQueryHandler(offer_photos_skip, pattern="^offer_photos_skip$"),
            ],

            O_PREVIEW: [
                CallbackQueryHandler(offer_publish, pattern="^offer_publish$"),
                CallbackQueryHandler(offer_cancel_cb, pattern="^offer_cancel$"),
            ],
        },
        fallbacks=[
            CommandHandler('cancel', cancel),
            MessageHandler(filters.Regex("^▶️ Старт$"), cancel),
            MessageHandler(filters.COMMAND, cancel),
        ],
    )
    application.add_handler(conv_handler)
    application.add_handler(offer_conv)
    application.add_handler(MessageHandler(filters.Regex("^▶️ Старт$"), start))
    application.add_handler(MessageHandler(filters.Regex("^📬 Подписаться$"), subscribe))
    application.add_handler(MessageHandler(filters.Regex("^ℹ️ Моя подписка$"), my_subscription))
    application.add_handler(MessageHandler(filters.Regex("^❌ Отписка$"), unsubscribe))
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("subscribe", subscribe))
    application.add_handler(CommandHandler("my_subscription", my_subscription))
    application.add_handler(CommandHandler("unsubscribe", unsubscribe))
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
