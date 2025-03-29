from django.contrib import admin
from .models import MESSAGE, INFO, Subscription

@admin.register(MESSAGE)
class MessageAdmin(admin.ModelAdmin):
    pass

@admin.register(INFO)
class InfoAdmin(admin.ModelAdmin):
    pass

@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ('user_id',)