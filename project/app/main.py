# app/main.py

import os
from telegram.ext import Application, CommandHandler
from .telegram_bot import start, add_habit, confirm, stats, list_habits
from .database import Base, engine

# Создаём таблицы (только для демо!)
Base.metadata.create_all(bind=engine)

def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN не задан в .env!")

    application = Application.builder().token(token).build()

    # Создаём обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("add_habit", add_habit))
    application.add_handler(CommandHandler("done", confirm))
    application.add_handler(CommandHandler("stats", stats))
    application.add_handler(CommandHandler("habits", list_habits))


    # Запуск
    application.run_polling()

if __name__ == "__main__":
    main()