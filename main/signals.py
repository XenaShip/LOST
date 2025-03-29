from django.db.models.signals import post_save
from django.dispatch import receiver
from asgiref.sync import sync_to_async
from main.models import MESSAGE
from main.services.subscriptions import check_subscriptions_for_new_ad

@receiver(post_save, sender=MESSAGE)
def check_new_message(sender, instance, created, **kwargs):
    if created:
        sync_to_async(check_subscriptions_for_new_ad)(instance)