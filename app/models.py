from datetime import datetime, date

from sqlalchemy import Column, Integer, String, Float, Date, DateTime, Text

from app.database import Base


class Workout(Base):
    __tablename__ = "workouts"

    id = Column(Integer, primary_key=True)
    log_date = Column(Date, default=date.today, index=True)
    exercise = Column(String, nullable=False)
    sets = Column(Integer, nullable=True)
    reps = Column(Integer, nullable=True)
    weight_kg = Column(Float, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Meal(Base):
    __tablename__ = "meals"

    id = Column(Integer, primary_key=True)
    log_date = Column(Date, default=date.today, index=True)
    food = Column(String, nullable=False)
    calories = Column(Integer, nullable=True)
    protein_g = Column(Float, nullable=True)
    carbs_g = Column(Float, nullable=True)
    fat_g = Column(Float, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class WaterIntake(Base):
    __tablename__ = "water_intake"

    id = Column(Integer, primary_key=True)
    log_date = Column(Date, default=date.today, index=True)
    amount_ml = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
