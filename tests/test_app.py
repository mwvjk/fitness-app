import os
from datetime import date
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

os.environ["DATABASE_URL"] = "sqlite://"

from app import database
from app.database import Base, get_db, make_engine
from app.main import app
from app.models import Meal, Workout


@pytest.fixture
def app_client(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(bind=engine)
    test_session = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        db = test_session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, follow_redirects=False) as client:
        yield client, test_session
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def test_workout_logging(app_client):
    client, test_session = app_client
    response = client.post(
        "/workouts",
        data={
            "exercise": "Squat",
            "sets": "3",
            "reps": "8",
            "weight_kg": "60",
            "log_date": date.today().isoformat(),
        },
    )

    assert response.status_code == 303
    page = client.get("/workouts")
    assert page.status_code == 200
    assert "Squat" in page.text

    with test_session() as db:
        workout = db.query(Workout).one()
        assert workout.exercise == "Squat"
        assert workout.sets == 3
        assert workout.reps == 8
        assert workout.weight_kg == 60


def test_meal_and_daily_calorie_logging(app_client):
    client, test_session = app_client
    response = client.post(
        "/meals",
        data={
            "food": "Skyr",
            "calories": "120",
            "protein_g": "17",
            "carbs_g": "8",
            "fat_g": "0.5",
            "log_date": date.today().isoformat(),
        },
    )

    assert response.status_code == 303
    page = client.get("/meals")
    assert page.status_code == 200
    assert "Today's total: 120 kcal" in page.text
    assert "Skyr" in page.text

    with test_session() as db:
        meal = db.query(Meal).one()
        assert meal.calories == 120
        assert meal.protein_g == 17


def test_get_db_closes_session(monkeypatch):
    session = Mock()
    monkeypatch.setattr(database, "SessionLocal", lambda: session)
    dependency = database.get_db()

    assert next(dependency) is session
    with pytest.raises(StopIteration):
        next(dependency)
    session.close.assert_called_once_with()