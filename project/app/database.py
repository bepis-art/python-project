from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

# URI базы данных из переменной окружения
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost/habits")

# Создаём движок SQLAlchemy — он управляет подключениями к БД
engine = create_engine(SQLALCHEMY_DATABASE_URL)

# Фабрика сессий — каждая сессия — "разговор" с БД
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Базовый класс для всех моделей
Base = declarative_base()