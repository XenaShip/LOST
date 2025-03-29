from tkinter.constants import CASCADE

from django.db import models

class MESSAGE(models.Model):
    text = models.TextField(blank=True, null=True)
    images = models.JSONField(blank=True, null=True)  # Для хранения списка URL изображений
    new_text = models.TextField(blank=True, null=True)
    def __str__(self):
        return self.text


class INFO(models.Model):
    message = models.ForeignKey(MESSAGE, on_delete=models.CASCADE)
    price = models.IntegerField(blank=True, null=True)
    rooms = models.IntegerField(blank=True, null=True)
    count_meters_flat = models.IntegerField(blank=True, null=True)
    location = models.CharField(blank=True, null=True)
    count_meters_metro = models.IntegerField(blank=True, null=True)
    adress = models.CharField(blank=True, null=True)


class CLIENT_INFO(models.Model):
    price = models.IntegerField(blank=True, null=True)
    rooms = models.IntegerField(blank=True, null=True)
    count_meters_flat = models.IntegerField(blank=True, null=True)
    location = models.CharField(blank=True, null=True)
    count_meters_metro = models.IntegerField(blank=True, null=True)
    adress = models.CharField(blank=True, null=True)
    phone_number = models.CharField(blank=True, null=True)
    tg = models.CharField(blank=True, null=True)
    images = models.JSONField(blank=True, null=True)
    description = models.CharField(blank=True, null=True)
    money_zalog = models.CharField(blank=True, null=True)


from django.db import models


class Subscription(models.Model):
    DISTRICT_CHOICES = [
        ('CAO', 'ЦАО'),
        ('YUAO', 'ЮАО'),
        ('SAO', 'САО'),
        ('ZAO', 'ЗАО'),
        ('VAO', 'ВАО'),
        ('ANY', 'Не важно'),
    ]

    user_id = models.BigIntegerField(unique=True)
    username = models.CharField(max_length=100, blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Параметры подписки
    min_price = models.IntegerField(blank=True, null=True)
    max_price = models.IntegerField(blank=True, null=True)
    min_rooms = models.IntegerField(blank=True, null=True)
    max_rooms = models.IntegerField(blank=True, null=True)
    district = models.CharField(
        max_length=4,
        choices=DISTRICT_CHOICES,
        default='ANY'
    )
    max_metro_distance = models.IntegerField(blank=True, null=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"Подписка {self.user_id}"