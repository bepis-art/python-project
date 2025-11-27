import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.database import SessionLocal
from app.models import User, Habit

def test_create_user_and_habit():
    db = SessionLocal()
    
    try:
        # Создаём пользователя
        user = User(telegram_id=999999, username="test_user")
        db.add(user)
        db.commit()
        db.refresh(user)
        assert user.id is not None
        assert user.telegram_id == 999999

        # Создаём привычку
        habit = Habit(
            description="Тестовая привычка",
            frequency_minutes=10,
            user_id=user.id
        )
        db.add(habit)
        db.commit()
        db.refresh(habit)
        assert habit.id is not None
        assert habit.description == "Тестовая привычка"
        assert habit.is_active is True

        print("Тест пройден: пользователь и привычка созданы")

    finally:
        # Удаляем созданные данные (очистка)
        if 'habit' in locals():
            db.delete(habit)
        if 'user' in locals():
            db.delete(user)
        db.commit()
        db.close()