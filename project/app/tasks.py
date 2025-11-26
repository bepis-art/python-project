# app/tasks.py

from celery import Celery
import os
from datetime import timedelta
from .database import SessionLocal
from .models import Completion, Habit, User
import logging
import httpx

celery_app = Celery(
    "habit_tracker",
    broker=os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0"),
    backend=os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")
)

logger = logging.getLogger(__name__)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

@celery_app.task
def create_reminder(habit_id: int):
    """Создаёт напоминание и отправляет уведомление в Telegram"""
    db = SessionLocal()
    try:
        # Создаём запись о напоминании
        completion = Completion(habit_id=habit_id)
        db.add(completion)
        db.commit()
        db.refresh(completion)

        # Получаем Telegram ID пользователя
        habit = db.query(Habit).filter(Habit.id == habit_id).first()
        user = db.query(User).filter(User.id == habit.user_id).first()

        logger.info(f"Отправка напоминания пользователю {user.telegram_id} для привычки {habit_id}")

        # Отправляем сообщение через Telegram Bot API
        if TELEGRAM_BOT_TOKEN and user.telegram_id:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            payload = {
                "chat_id": user.telegram_id,
                "text": f"🔔 Напоминание!\n\nВаша привычка: *{habit.description}*\n\nНажмите /done, если выполнили!",
                "parse_mode": "Markdown"
            }
            try:
                httpx.post(url, json=payload, timeout=10)
            except Exception as e:
                logger.error(f"Не удалось отправить сообщение: {e}")

    except Exception as e:
        logger.error(f"Ошибка в create_reminder: {e}")
        db.rollback()
    finally:
        db.close()

    # Планируем следующее напоминание
    schedule_next_reminder(habit_id)

def schedule_next_reminder(habit_id: int):
    db = SessionLocal()
    try:
        habit = db.query(Habit).filter(Habit.id == habit_id).first()
        if habit:
            create_reminder.apply_async(
                args=[habit_id],
                countdown=habit.frequency_minutes * 60
            )
    finally:
        db.close()