import logging
from telegram import Update
from telegram.ext import ContextTypes
from .database import SessionLocal
from .models import User, Habit, Completion
from .tasks import schedule_next_reminder
from datetime import datetime, timedelta, timezone

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
            await update.message.reply_text(
                "✅ Добро пожаловать! Вы зарегистрированы.\n\n"
                "Используйте:\n"
                "/add_habit — добавить привычку\n"
                "/habits — посмотреть привычки\n"
                "/done — подтвердить выполнение\n"
                "/stats — статистика за неделю"
            )
        else:
            await update.message.reply_text(
                "👋 С возвращением!\n\n"
                "Доступные команды:\n"
                "/add_habit — добавить привычку\n"
                "/habits — список привычек\n"
                "/done — подтвердить выполнение\n"
                "/stats — статистика"
            )
    finally:
        db.close()

async def add_habit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /add_habit — добавление привычки"""
    if not context.args:
        await update.message.reply_text(
            "Использование:\n"
            "/add_habit <описание> <интервал>\n\n"
            "Интервал: 1, 5 или 60 (минут)\n"
            "Пример: /add_habit Читать 30 минут 60"
        )
        return

    try:
        # Последний аргумент — интервал, остальное — описание
        frequency = int(context.args[-1])
        if frequency not in [1, 5, 60]:
            raise ValueError("Неверный интервал")
        description = " ".join(context.args[:-1]).strip()
        if not description:
            raise ValueError("Описание пустое")
    except (ValueError, IndexError):
        await update.message.reply_text("❌ Неверный формат. Пример: /add_habit 'Пить воду' 5")
        return

    telegram_id = update.effective_user.id
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        if not user:
            await update.message.reply_text("Пожалуйста, сначала отправьте /start")
            return

        habit = Habit(description=description, frequency_minutes=frequency, user_id=user.id)
        db.add(habit)
        db.commit()
        db.refresh(habit)

        # Запуск первого напоминания
        schedule_next_reminder(habit.id)

        freq_text = {1: "каждую минуту", 5: "каждые 5 минут", 60: "каждый час"}[frequency]
        await update.message.reply_text(f"✅ Привычка добавлена:\n«{description}» — {freq_text}")
    finally:
        db.close()

async def confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /done — подтверждение выполнения последнего напоминания"""
    telegram_id = update.effective_user.id
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        if not user:
            await update.message.reply_text("Пожалуйста, сначала отправьте /start")
            return

        # Ищем последнее неподтверждённое напоминание за последние 2 минуты
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=2)
        completion = (
            db.query(Completion)
            .join(Habit)
            .filter(
                Habit.user_id == user.id,
                Completion.confirmed == False,
                Completion.completed_at >= cutoff
            )
            .order_by(Completion.completed_at.desc())
            .first()
        )

        if completion:
            completion.confirmed = True
            db.commit()
            habit = db.query(Habit).filter(Habit.id == completion.habit_id).first()
            await update.message.reply_text(f"✅ Отлично! Привычка «{habit.description}» засчитана.")
        else:
            await update.message.reply_text(
                "❌ Нет активных напоминаний для подтверждения.\n"
                "Напоминание действует 2 минуты после отправки."
            )
    finally:
        db.close()

async def list_habits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /habits — список всех привычек пользователя"""
    telegram_id = update.effective_user.id
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        if not user:
            await update.message.reply_text("Пожалуйста, сначала отправьте /start")
            return

        habits = db.query(Habit).filter(Habit.user_id == user.id).all()
        if not habits:
            await update.message.reply_text("У вас пока нет привычек. Добавьте через /add_habit")
        else:
            text = "📋 Ваши привычки:\n\n"
            freq_map = {1: "каждую минуту", 5: "каждые 5 минут", 60: "каждый час"}
            for i, h in enumerate(habits, 1):
                freq = freq_map.get(h.frequency_minutes, f"каждые {h.frequency_minutes} мин")
                text += f"{i}. «{h.description}» — {freq}\n"
            await update.message.reply_text(text)
    finally:
        db.close()

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /stats — статистика за последнюю неделю"""
    from datetime import datetime, timedelta, timezone
    telegram_id = update.effective_user.id
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        if not user:
            await update.message.reply_text("Пожалуйста, сначала отправьте /start")
            return

        one_week_ago = datetime.now(timezone.utc) - timedelta(days=7)

        total = (
            db.query(Completion)
            .join(Habit)
            .filter(Habit.user_id == user.id, Completion.completed_at >= one_week_ago)
            .count()
        )
        confirmed = (
            db.query(Completion)
            .join(Habit)
            .filter(
                Habit.user_id == user.id,
                Completion.completed_at >= one_week_ago,
                Completion.confirmed == True
            )
            .count()
        )

        if total == 0:
            await update.message.reply_text("📊 За последнюю неделю у вас не было напоминаний.")
        else:
            missed = total - confirmed
            percent = round(confirmed / total * 100, 1)
            await update.message.reply_text(
                f"📊 Статистика за неделю:\n\n"
                f"✅ Выполнено: {confirmed}\n"
                f"❌ Пропущено: {missed}\n"
                f"🎯 Процент выполнения: {percent}%"
            )
    finally:
        db.close()