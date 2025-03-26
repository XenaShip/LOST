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