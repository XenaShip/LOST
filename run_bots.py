import subprocess
import sys
import time


def run_bot(bot_file):
    """Запускает бота в отдельном процессе"""
    print(f"Запуск бота из файла: {bot_file}")
    subprocess.Popen([sys.executable, bot_file])


if __name__ == '__main__':
    # Список файлов с ботами
    bot_files = ['bot_3_2.py', 'bot.py']  # Добавьте все ваши бот-файлы

    # Запускаем каждого бота в отдельном процессе
    for bot_file in bot_files:
        run_bot(bot_file)

    # Бесконечный цикл, чтобы главный процесс не завершался
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nОстановка всех ботов...")