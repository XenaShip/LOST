import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
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

from main.models import Subscription

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Состояния диалога
PRICE, ROOMS, FLAT_AREA, DISTRICT, METRO_DISTANCE, CONFIRM = range(6)


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
        [InlineKeyboardButton("До 5 минут (400м)", callback_data="metro_400")],
        [InlineKeyboardButton("До 10 минут (800м)", callback_data="metro_800")],
        [InlineKeyboardButton("До 15 минут (1200м)", callback_data="metro_1200")],
        [InlineKeyboardButton("До 20 минут (1600м)", callback_data="metro_1600")],
        [InlineKeyboardButton("Не важно", callback_data="metro_any")],
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
        [KeyboardButton("❌ Отписка")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


# --- Работа с БД ---
@sync_to_async
def get_subscription(user_id):
    try:
        return Subscription.objects.get(user_id=user_id)
    except Subscription.DoesNotExist:
        return None


@sync_to_async
def update_or_create_subscription(user_id, username, params):
    return Subscription.objects.update_or_create(
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
            'max_metro_distance': params.get('max_metro_distance'),
            'is_active': True
        }
    )


@sync_to_async
def deactivate_subscription(user_id):
    try:
        sub = Subscription.objects.get(user_id=user_id)
        sub.is_active = False
        sub.save()
        return True
    except Subscription.DoesNotExist:
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

    data = query.data.split('_')
    if data[1] == 'any':
        context.user_data['max_metro_distance'] = None
    else:
        context.user_data['max_metro_distance'] = int(data[1])

    district_name = dict(Subscription.DISTRICT_CHOICES).get(
        context.user_data.get('district'), 'Не важно'
    )

    summary = (
        "✅ Проверьте параметры подписки:\n\n"
        f"• Цена: {context.user_data.get('min_price', 'не важно')} - {context.user_data.get('max_price', 'не важно')} руб\n"
        f"• Комнат: {context.user_data.get('min_rooms', 'не важно')}-{context.user_data.get('max_rooms', 'не важно')}\n"
        f"• Площадь: {context.user_data.get('min_flat', 'не важно')}-{context.user_data.get('max_flat', 'не важно')} м²\n"
        f"• Округ: {district_name}\n"
        f"• До метро: ≤{context.user_data.get('max_metro_distance', 'не важно')} м\n\n"
        "Подтвердите ваш выбор:"
    )

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
        district_name = dict(Subscription.DISTRICT_CHOICES).get(sub.district, 'Не важно')
        text = (
            "📋 Ваша текущая подписка:\n\n"
            f"• Цена: {sub.min_price or 'не важно'} - {sub.max_price or 'не важно'} руб\n"
            f"• Комнат: {sub.min_rooms or 'не важно'}-{sub.max_rooms or 'не важно'}\n"
            f"• Площадь: {sub.min_flat or 'не важно'}-{sub.max_flat or 'не важно'} м²\n"
            f"• Округ: {district_name}\n"
            f"• До метро: ≤{sub.max_metro_distance or 'не важно'} м\n\n"
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
    application = Application.builder().token(os.getenv("TOKEN3")).build()

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

    application.add_handler(conv_handler)
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
