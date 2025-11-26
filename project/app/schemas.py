from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class UserCreate(BaseModel):
    telegram_id: int
    username: Optional[str] = None

class HabitCreate(BaseModel):
    description: str
    frequency_minutes: int

class CompletionResponse(BaseModel):
    id: int
    habit_id: int
    completed_at: datetime
    confirmed: bool

    class Config:
        from_attributes = True  # позволяет работать с ORM-объектами