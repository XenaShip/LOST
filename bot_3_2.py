import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
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
PRICE, ROOMS, DISTRICT, METRO_DISTANCE, CONFIRM = range(5)


# Клавиатура выбора округа
def get_district_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("ЦАО", callback_data="CAO")],
        [InlineKeyboardButton("ЮАО", callback_data="YUAO")],
        [InlineKeyboardButton("САО", callback_data="SAO")],
        [InlineKeyboardButton("ЗАО", callback_data="ZAO")],
        [InlineKeyboardButton("ВАО", callback_data="VAO")],
        [InlineKeyboardButton("Не важно", callback_data="ANY")],
    ])


# Асинхронные операции с БД
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


# Команды бота
async def start(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text(
        "🏡 Бот подписки на объявления о недвижимости\n\n"
        "Доступные команды:\n"
        "/subscribe - Настроить подписку\n"
        "/my_subscription - Просмотреть текущую подписку\n"
        "/unsubscribe - Отписаться от уведомлений"
    )


async def subscribe(update: Update, context: CallbackContext) -> int:
    context.user_data.clear()
    await update.message.reply_text(
        "💰 Укажите ваш бюджет в рублях (мин и макс через пробел):\n"
        "Пример: 5000000 10000000\n"
        "Или напишите 'не важно'"
    )
    return PRICE


async def get_price(update: Update, context: CallbackContext) -> int:
    text = update.message.text.lower()
    if text == 'не важно':
        context.user_data['min_price'] = None
        context.user_data['max_price'] = None
    else:
        try:
            min_price, max_price = map(int, text.split())
            context.user_data['min_price'] = min_price
            context.user_data['max_price'] = max_price
        except:
            await update.message.reply_text("❌ Неверный формат. Попробуйте снова")
            return PRICE

    await update.message.reply_text(
        "🚪 Сколько комнат вам нужно?\n"
        "Формат: от до\nПример: 1 3\n"
        "Или напишите 'не важно'"
    )
    return ROOMS


async def get_rooms(update: Update, context: CallbackContext) -> int:
    text = update.message.text.lower()
    if text == 'не важно':
        context.user_data['min_rooms'] = None
        context.user_data['max_rooms'] = None
    else:
        try:
            rooms = list(map(int, text.split()))
            context.user_data['min_rooms'] = rooms[0]
            context.user_data['max_rooms'] = rooms[1] if len(rooms) > 1 else rooms[0]
        except:
            await update.message.reply_text("❌ Неверный формат. Попробуйте снова")
            return ROOMS

    await update.message.reply_text(
        "🗺️ Выберите округ:",
        reply_markup=get_district_keyboard()
    )
    return DISTRICT


async def get_district(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data['district'] = query.data
    await query.edit_message_text(f"Выбран округ: {dict(Subscription.DISTRICT_CHOICES)[query.data]}")

    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text="🚇 Укажите максимальное расстояние до метро в метрах:\n"
             "Пример: 500\nИли напишите 'не важно'"
    )
    return METRO_DISTANCE


async def get_metro_distance(update: Update, context: CallbackContext) -> int:
    text = update.message.text.lower()
    if text == 'не важно':
        context.user_data['max_metro_distance'] = None
    else:
        try:
            context.user_data['max_metro_distance'] = int(text)
        except:
            await update.message.reply_text("❌ Введите число метров")
            return METRO_DISTANCE

    # Формируем сводку
    data = context.user_data
    district_name = dict(Subscription.DISTRICT_CHOICES).get(data.get('district'), 'Не важно')

    text = (
        "✅ Ваши критерии подписки:\n\n"
        f"• Цена: {data.get('min_price', 'не важно')} - {data.get('max_price', 'не важно')} руб\n"
        f"• Комнат: {data.get('min_rooms', 'не важно')}-{data.get('max_rooms', 'не важно')}\n"
        f"• Округ: {district_name}\n"
        f"• До метро: ≤{data.get('max_metro_distance', 'не важно')} м\n\n"
        "Сохранить подписку? (да/нет)"
    )

    await update.message.reply_text(text)
    return CONFIRM


async def confirm_subscription(update: Update, context: CallbackContext) -> int:
    if update.message.text.lower() == 'да':
        user = update.effective_user
        await update_or_create_subscription(
            user_id=user.id,
            username=user.username,
            params=context.user_data
        )
        await update.message.reply_text("🎉 Подписка успешно сохранена!")
    else:
        await update.message.reply_text("Настройка подписки отменена")

    return ConversationHandler.END


async def cancel(update: Update, context: CallbackContext) -> int:
    await update.message.reply_text("Настройка подписки отменена")
    return ConversationHandler.END


async def my_subscription(update: Update, context: CallbackContext) -> None:
    sub = await get_subscription(update.effective_user.id)
    if sub:
        district_name = dict(Subscription.DISTRICT_CHOICES).get(sub.district, 'Не важно')

        text = (
            "📋 Ваша текущая подписка:\n\n"
            f"• Цена: {sub.min_price or 'не важно'} - {sub.max_price or 'не важно'} руб\n"
            f"• Комнат: {sub.min_rooms or 'не важно'}-{sub.max_rooms or 'не важно'}\n"
            f"• Округ: {district_name}\n"
            f"• До метро: ≤{sub.max_metro_distance or 'не важно'} м\n\n"
            "Изменить параметры: /subscribe\n"
            "Отписаться: /unsubscribe"
        )
        await update.message.reply_text(text)
    else:
        await update.message.reply_text("У вас нет активной подписки. Настройте её через /subscribe")


async def unsubscribe(update: Update, context: CallbackContext) -> None:
    success = await deactivate_subscription(update.effective_user.id)
    if success:
        await update.message.reply_text("🔕 Вы успешно отписались от уведомлений")
    else:
        await update.message.reply_text("У вас нет активной подписки")


def main() -> None:
    application = Application.builder().token("7829685367:AAFdmJo316UlwM9HcUEpr0NxhOc8lPOU_b0").build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('subscribe', subscribe)],
        states={
            PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_price)],
            ROOMS: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_rooms)],
            DISTRICT: [CallbackQueryHandler(get_district)],
            METRO_DISTANCE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_metro_distance)],
            CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_subscription)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("my_subscription", my_subscription))
    application.add_handler(CommandHandler("unsubscribe", unsubscribe))

    application.run_polling()


if __name__ == '__main__':
    main()