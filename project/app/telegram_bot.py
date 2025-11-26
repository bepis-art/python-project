import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from .database import SessionLocal
from .models import User, Habit, Completion
from .tasks import schedule_next_reminder
from datetime import datetime

# Настройка логгера
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start — регистрация пользователя"""
    telegram_id = update.effective_user.id
    username = update.effective_user.username

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        if not user:
            user = User(telegram_id=telegram_id, username=username)
            db.add(user)
            db.commit()
            db.refresh(user)
            await update.message.reply_text("✅ Вы зарегистрированы! Используйте /add_habit для добавления привычки.")
        else:
            await update.message.reply_text("👋 С возвращением! Используйте /add_habit, /habits или /stats.")
    finally:
        db.close()

async def add_habit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /add_habit — добавление привычки"""
    if not context.args:
        await update.message.reply_text("Использование: /add_habit <описание> <интервал_в_минутах>\nПример: /add_habit 'Читать 30 мин' 60")
        return

    try:
        description = " ".join(context.args[:-1])
        frequency = int(context.args[-1])
        if frequency not in [1, 5, 60]:
            raise ValueError
    except (ValueError, IndexError):
        await update.message.reply_text("❌ Неверный формат. Интервал: 1, 5 или 60 минут.")
        return

    telegram_id = update.effective_user.id
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        habit = Habit(description=description, frequency_minutes=frequency, user_id=user.id)
        db.add(habit)
        db.commit()
        db.refresh(habit)

        # Запуск первого напоминания
        schedule_next_reminder(habit.id)

        await update.message.reply_text(f"✅ Привычка добавлена: '{description}' (каждые {frequency} мин)")
    finally:
        db.close()

async def confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /done — подтверждение выполнения последнего напоминания"""
    telegram_id = update.effective_user.id
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        # Находим последнее неподтверждённое напоминание за последние 2 минуты
        completion = (
            db.query(Completion)
            .join(Habit)
            .filter(
                Habit.user_id == user.id,
                Completion.confirmed == False,
                Completion.completed_at >= datetime.utcnow().timestamp() - 120  # 2 мин на подтверждение
            )
            .order_by(Completion.completed_at.desc())
            .first()
        )
        if completion:
            completion.confirmed = True
            db.commit()
            await update.message.reply_text("✅ Отлично! Привычка засчитана.")
        else:
            await update.message.reply_text("❌ Нет активных напоминаний для подтверждения.")
    finally:
        db.close()

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /stats — статистика за неделю"""
    from datetime import timedelta, datetime as dt
    telegram_id = update.effective_user.id
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        one_week_ago = dt.utcnow() - timedelta(days=7)

        total = db.query(Completion).join(Habit).filter(Habit.user_id == user.id, Completion.completed_at >= one_week_ago).count()
        confirmed = db.query(Completion).join(Habit).filter(Habit.user_id == user.id, Completion.completed_at >= one_week_ago, Completion.confirmed == True).count()

        if total == 0:
            await update.message.reply_text("📊 За неделю у вас ещё не было напоминаний.")
        else:
            percent = round(confirmed / total * 100, 1)
            await update.message.reply_text(f"📊 Статистика за неделю:\n✅ Подтверждено: {confirmed}\n❌ Пропущено: {total - confirmed}\n🎯 Процент выполнения: {percent}%")
    finally:
        db.close()