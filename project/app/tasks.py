from celery import Celery
import os
from datetime import timedelta
from .database import SessionLocal
from .models import Completion
import logging

# Настройка Celery
celery_app = Celery(
    "habit_tracker",
    broker=os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0"),
    backend=os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")
)

logger = logging.getLogger(__name__)

@celery_app.task
def create_reminder(habit_id: int):
    """Создаёт запись о напоминании в БД и планирует следующее"""
    db = SessionLocal()
    try:
        completion = Completion(habit_id=habit_id)
        db.add(completion)
        db.commit()
        logger.info(f"Создано напоминание для привычки {habit_id}")
    finally:
        db.close()

    # Планируем следующее напоминание через frequency_minutes
    schedule_next_reminder(habit_id)

def schedule_next_reminder(habit_id: int):
    """Планирует следующее напоминание через нужный интервал"""
    db = SessionLocal()
    try:
        from .models import Habit
        habit = db.query(Habit).filter(Habit.id == habit_id).first()
        if habit:
            # Запускаем задачу с задержкой
            create_reminder.apply_async(
                args=[habit_id],
                countdown=habit.frequency_minutes * 60  # переводим минуты в секунды
            )
    finally:
        db.close()