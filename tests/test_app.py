import os
from datetime import date
from unittest.mock import Mock

import pytest
from alembic import command
from alembic.config import Config
from pydantic import ValidationError
from fastapi.testclient import TestClient
from sqlalchemy import inspect
from sqlalchemy.orm import sessionmaker

os.environ["DATABASE_URL"] = "sqlite://"

from app import database
from app.config import Settings
from app.database import Base, get_db, make_engine
from app.main import app
from app.models import Meal, Workout


def test_database_url_is_required_from_environment(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_alembic_initial_migration_creates_schema(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path / 'migration.db'}")
    config = Config("alembic.ini")
    with engine.connect() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")

    inspector = inspect(engine)
    assert {"meals", "workouts", "alembic_version"}.issubset(
        set(inspector.get_table_names())
    )
    engine.dispose()


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


@pytest.mark.parametrize(
    ("protein_g", "carbs_g", "fat_g"),
    [(1, 0, 0), (0, 1, 0), (0, 0, 1)],
)
def test_zero_calories_rejected_when_macro_is_positive(app_client, protein_g, carbs_g, fat_g):
    client, test_session = app_client
    response = client.post(
        "/meals",
        data={
            "food": "Test food",
            "calories": "0",
            "protein_g": str(protein_g),
            "carbs_g": str(carbs_g),
            "fat_g": str(fat_g),
            "log_date": date.today().isoformat(),
        },
    )

    assert response.status_code == 400
    assert (
        '<p role="alert">Calories must be greater than 0 when macros are entered.</p>'
        not in response.text
    )
    with test_session() as db:
        assert db.query(Meal).count() == 0


def test_zero_calories_allowed_when_all_macros_are_zero(app_client):
    client, test_session = app_client
    response = client.post(
        "/meals",
        data={
            "food": "Water",
            "calories": "0",
            "protein_g": "0",
            "carbs_g": "0",
            "fat_g": "0",
            "log_date": date.today().isoformat(),
        },
    )

    assert response.status_code == 303
    with test_session() as db:
        meal = db.query(Meal).one()
        assert meal.calories == 0


def test_get_db_closes_session(monkeypatch):
    session = Mock()
    monkeypatch.setattr(database, "SessionLocal", lambda: session)
    dependency = database.get_db()

    assert next(dependency) is session
    with pytest.raises(StopIteration):
        next(dependency)
    session.close.assert_called_once_with()