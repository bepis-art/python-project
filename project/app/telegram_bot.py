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
                "Команды:\n"
                "/add_habit — добавить привычку\n"
                "/habits — посмотреть привычки и статистику\n"
                "/pause_habit — приостановить привычку\n"
                "/resume_habit — возобновить привычку\n"
                "/delete_habit — удалить привычку\n"
                "/stats — статистика за последнюю неделю\n"
                "/reset_stats — обнулить всю статистику\n"
                "/done — подтвердить выполнение\n\n"
                "ℹ️ Интервал в /add_habit указывается в минутах (от 1 до 1440)."
            )
        else:
            await update.message.reply_text(
                "👋 С возвращением!\n\n"
                "Команды:\n"
                "/add_habit — добавить привычку\n"
                "/habits — посмотреть привычки и статистику\n"
                "/pause_habit — приостановить привычку\n"
                "/resume_habit — возобновить привычку\n"
                "/delete_habit — удалить привычку\n"
                "/stats — статистика за последнюю неделю\n"
                "/reset_stats — обнулить всю статистику\n"
                "/done — подтвердить выполнение\n\n"
                "ℹ️ Интервал в /add_habit указывается в минутах (от 1 до 1440)."

            )
    finally:
        db.close()

async def add_habit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /add_habit — добавление привычки"""
    if not context.args:
        await update.message.reply_text(
            "Использование:\n"
            "/add_habit <описание> <интервал>\n\n"
            "Интервал: от 1 до 1440 (минут)\n"
            "Пример: /add_habit Читать 30 минут 41"
        )
        return

    try:
        # Последний аргумент — интервал, остальное — описание
        frequency = int(context.args[-1])
        if frequency < 1 or frequency > 1440:
            raise ValueError("Интервал должен быть от 1 до 1440 минут (24 часа)")
        description = " ".join(context.args[:-1]).strip()
        if not description:
            raise ValueError("Описание пустое")
    except (ValueError, IndexError):
        await update.message.reply_text("❌ Неверный формат.\n\n"
                                        "Использование:\n"
                                        "/add_habit <описание> <интервал_в_минутах>\n\n"
                                        "Примеры:\n"
                                        "/add_habit Выпивать стакан воды 30\n"
                                        "/add_habit Медитация 10\n\n"
                                        "Допустимый интервал: от 1 до 1440 минут (24 часа).")
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

        def format_interval(minutes: int) -> str:
            if minutes == 1:
                return "каждую минуту"
            elif minutes < 60:
                return f"каждые {minutes} мин"
            elif minutes % 60 == 0:
                hours = minutes // 60
                return f"каждые {hours} ч"
            else:
                hours = minutes // 60
                mins = minutes % 60
                return f"каждые {hours} ч {mins} мин"

        freq_text = format_interval(frequency)
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

        # Ищем последнее неподтверждённое напоминание за последнюю минуту
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=1)
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
    """Команда /habits — список всех привычек с мини-статистикой"""
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
            return

        # Вспомогательная функция для красивого отображения интервала
        def format_interval(minutes: int) -> str:
            if minutes == 1:
                return "каждую минуту"
            elif minutes < 60:
                return f"каждые {minutes} мин"
            elif minutes % 60 == 0:
                hours = minutes // 60
                return f"каждые {hours} ч"
            else:
                hours = minutes // 60
                mins = minutes % 60
                return f"каждые {hours} ч {mins} мин"

        text = "📋 Ваши привычки:\n\n"

        for i, h in enumerate(habits, 1):
            status = "▶️" if h.is_active else "⏸️"
            freq = format_interval(h.frequency_minutes)
            
            # Статистика: всего напоминаний и подтверждённых
            total = db.query(Completion).filter(Completion.habit_id == h.id).count()
            confirmed = db.query(Completion).filter(
                Completion.habit_id == h.id, 
                Completion.confirmed == True
            ).count()
            
            if total == 0:
                progress = "—"
            else:
                progress = f"{confirmed}/{total} ({round(confirmed / total * 100)}%)"

            # Экранируем возможные спецсимволы в описании (на всякий случай)
            description = h.description.replace("_", "\\_").replace("*", "\\*").replace("`", "\\`")
            text += f"{i}. {status} «{description}» — {freq}\n   Статистика: {progress}\n\n"

        text += (
            "\nКоманды:\n"
            "/pause_habit <номер> — приостановить\n"
            "/resume_habit <номер> — возобновить\n"
            "/delete_habit <номер> — удалить"
        )
        await update.message.reply_text(text)

    except Exception as e:
        logger.error(f"Ошибка в /habits: {e}")
        await update.message.reply_text("❌ Не удалось загрузить список привычек.")
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

async def delete_habit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /delete_habit — удаление привычки по номеру"""
    if not context.args:
        await update.message.reply_text(
            "Использование: /delete_habit <номер>\n\n"
            "Сначала посмотрите список привычек: /habits"
        )
        return

    try:
        habit_index = int(context.args[0]) - 1  # пользователь вводит с 1
        if habit_index < 0:
            raise ValueError
    except (ValueError, IndexError):
        await update.message.reply_text("❌ Неверный номер. Пример: /delete_habit 1")
        return

    telegram_id = update.effective_user.id
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        if not user:
            await update.message.reply_text("Пожалуйста, сначала отправьте /start")
            return

        habits = db.query(Habit).filter(Habit.user_id == user.id).all()
        if not habits:
            await update.message.reply_text("У вас нет привычек.")
            return

        if habit_index >= len(habits):
            await update.message.reply_text(f"❌ Нет привычки под номером {habit_index + 1}.")
            return

        habit_to_delete = habits[habit_index]
        habit_desc = habit_to_delete.description

        # Удаляем саму привычку и ВСЮ связанную статистику
        db.query(Completion).filter(Completion.habit_id == habit_to_delete.id).delete()
        db.delete(habit_to_delete)
        db.commit()

        await update.message.reply_text(f"🗑️ Привычка «{habit_desc}» удалена вместе со всей статистикой.")
    finally:
        db.close()


async def reset_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /reset_stats — полная очистка статистики (всех напоминаний)"""
    telegram_id = update.effective_user.id
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        if not user:
            await update.message.reply_text("Пожалуйста, сначала отправьте /start")
            return

        habit_ids = db.query(Habit.id).filter(Habit.user_id == user.id).all()
        habit_ids = [h.id for h in habit_ids]

        if not habit_ids:
            await update.message.reply_text("У вас нет привычек, поэтому статистика пуста.")
            return

        # Удаляем все напоминания по этим habit_id
        deleted = db.query(Completion).filter(Completion.habit_id.in_(habit_ids)).delete(synchronize_session=False)
        db.commit()

        if deleted == 0:
            await update.message.reply_text("📊 У вас ещё нет записей напоминаний для сброса.")
        else:
            await update.message.reply_text(f"✅ Статистика сброшена! Удалено {deleted} записей напоминаний.")
    except Exception as e:
        db.rollback()
        logger.error(f"Ошибка при сбросе статистики: {e}")
        await update.message.reply_text("❌ Произошла ошибка при сбросе статистики. Попробуйте позже.")
    finally:
        db.close()

async def pause_habit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /pause_habit — остановить напоминания для привычки"""
    if not context.args:
        await update.message.reply_text(
            "Использование: /pause_habit <номер>\n\nСписок: /habits"
        )
        return

    try:
        habit_index = int(context.args[0]) - 1
        if habit_index < 0:
            raise ValueError
    except (ValueError, IndexError):
        await update.message.reply_text("❌ Неверный номер. Пример: /pause_habit 1")
        return

    telegram_id = update.effective_user.id
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        if not user:
            await update.message.reply_text("Пожалуйста, сначала отправьте /start")
            return

        habits = db.query(Habit).filter(Habit.user_id == user.id).all()
        if not habits:
            await update.message.reply_text("У вас нет привычек.")
            return

        if habit_index >= len(habits):
            await update.message.reply_text(f"❌ Нет привычки под номером {habit_index + 1}.")
            return

        habit = habits[habit_index]
        if not habit.is_active:
            await update.message.reply_text(f"⏸️ Привычка «{habit.description}» уже приостановлена.")
            return

        habit.is_active = False
        db.commit()

        await update.message.reply_text(f"⏸️ Напоминания для «{habit.description}» приостановлены.")
    finally:
        db.close()


async def resume_habit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /resume_habit — возобновить напоминания для привычки"""
    if not context.args:
        await update.message.reply_text(
            "Использование: /resume_habit <номер>\n\nСписок: /habits"
        )
        return

    try:
        habit_index = int(context.args[0]) - 1
        if habit_index < 0:
            raise ValueError
    except (ValueError, IndexError):
        await update.message.reply_text("❌ Неверный номер. Пример: /resume_habit 1")
        return

    telegram_id = update.effective_user.id
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        if not user:
            await update.message.reply_text("Пожалуйста, сначала отправьте /start")
            return

        habits = db.query(Habit).filter(Habit.user_id == user.id).all()
        if not habits:
            await update.message.reply_text("У вас нет привычек.")
            return

        if habit_index >= len(habits):
            await update.message.reply_text(f"❌ Нет привычки под номером {habit_index + 1}.")
            return

        habit = habits[habit_index]
        if habit.is_active:
            await update.message.reply_text(f"▶️ Привычка «{habit.description}» уже активна.")
            return

        habit.is_active = True
        db.commit()

        # Запускаем напоминание **сейчас** (или через интервал)
        from .tasks import schedule_first_reminder
        schedule_first_reminder.delay(habit.id, habit.frequency_minutes)

        await update.message.reply_text(f"▶️ Напоминания для «{habit.description}» возобновлены.")
    finally:
        db.close()