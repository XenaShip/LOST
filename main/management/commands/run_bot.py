from django.core.management.base import BaseCommand
from bot import Command as BotCommand  # Замените `your_app` на имя вашего приложения

class Command(BaseCommand):
    help = 'Запуск Telegram бота'

    def handle(self, *args, **options):
        bot_command = BotCommand()
        bot_command.handle(*args, **options)