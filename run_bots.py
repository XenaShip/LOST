import multiprocessing
import os
import sys
import time
from importlib import import_module


def run_bot(bot_file):
    """Запускает бота в отдельном процессе"""

    # Выносим код в глобальную область видимости модуля
    def bot_runner():
        # Инициализация Django
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
        import django
        django.setup()

        # Динамический импорт main функции из файла бота
        module_name = bot_file.replace('.py', '')
        module = import_module(module_name)
        module.main()

    # Для Windows обязательно используем spawn
    ctx = multiprocessing.get_context('spawn')
    process = ctx.Process(target=bot_runner)
    process.start()
    return process


if __name__ == '__main__':
    bot_files = ['bot_3_2.py', 'bot.py']  # Ваши файлы с ботами

    processes = []
    try:
        print("Запуск ботов...")
        for bot_file in bot_files:
            p = run_bot(bot_file)
            processes.append(p)
            print(f"Бот {bot_file} запущен (PID: {p.pid})")
            time.sleep(1)  # Небольшая задержка между запусками

        # Бесконечный цикл для поддержания работы
        while True:
            time.sleep(5)
            # Проверяем работоспособность процессов
            if not any(p.is_alive() for p in processes):
                print("Все процессы завершились")
                break

    except KeyboardInterrupt:
        print("\nОстановка ботов...")
        for p in processes:
            if p.is_alive():
                p.terminate()
        for p in processes:
            p.join()
    print("Работа завершена")