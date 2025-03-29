from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .services.subscriptions import create_or_update_subscription

@csrf_exempt
def telegram_webhook(request):
    if request.method == 'POST':
        data = request.json()
        # Обработка входящих сообщений
        return JsonResponse({'status': 'ok'})