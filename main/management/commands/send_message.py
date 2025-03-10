from django.core.management.base import BaseCommand
from main.tasks import process_and_send_messages

class Command(BaseCommand):
    help = "Запускает обработку сообщений и отправку в Telegram"

    def handle(self, *args, **kwargs):
        process_and_send_messages.delay()
        self.stdout.write(self.style.SUCCESS("Задача отправлена в Celery!"))
