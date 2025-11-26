import os
from telegram.ext import Application, CommandHandler
from .telegram_bot import start, add_habit, confirm, list_habits, stats, delete_habit, reset_stats, pause_habit, resume_habit 
from .database import Base, engine

Base.metadata.create_all(bind=engine)

def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN не задан!")

    application = Application.builder().token(token).build()

    # ДОБАВЛЯЕМ ХЕНДЛЕРЫ — ОДИН РАЗ КАЖДЫЙ!
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("add_habit", add_habit))
    application.add_handler(CommandHandler("done", confirm))
    application.add_handler(CommandHandler("habits", list_habits))
    application.add_handler(CommandHandler("stats", stats))
    application.add_handler(CommandHandler("delete_habit", delete_habit))
    application.add_handler(CommandHandler("reset_stats", reset_stats))
    application.add_handler(CommandHandler("pause_habit", pause_habit))
    application.add_handler(CommandHandler("resume_habit", resume_habit))

    application.run_polling()

if __name__ == "__main__":
    main()