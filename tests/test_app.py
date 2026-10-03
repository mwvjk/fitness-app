import os
from datetime import date, timedelta
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
from app.models import Meal, WaterIntake, Workout


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
    assert {"meals", "workouts", "water_intake", "alembic_version"}.issubset(
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


def test_workout_can_be_edited(app_client):
    client, test_session = app_client
    with test_session() as db:
        workout = Workout(
            log_date=date.today(),
            exercise="Squat",
            sets=3,
            reps=8,
            weight_kg=60,
        )
        db.add(workout)
        db.commit()
        workout_id = workout.id

    response = client.post(
        f"/workouts/{workout_id}/edit",
        data={
            "exercise": "Front squat",
            "sets": "4",
            "reps": "6",
            "weight_kg": "70",
            "log_date": "2026-10-01",
            "notes": "Updated",
        },
    )

    assert response.status_code == 303
    with test_session() as db:
        workout = db.get(Workout, workout_id)
        assert workout.exercise == "Front squat"
        assert workout.sets == 4
        assert workout.reps == 6
        assert workout.weight_kg == 70
        assert workout.log_date == date(2026, 10, 1)
        assert workout.notes == "Updated"


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
    with test_session() as db:
        db.add(
            Meal(
                log_date=date.today(),
                food="Fruit",
                calories=30,
                protein_g=3,
                carbs_g=6,
                fat_g=0.2,
            )
        )
        db.add(
            Meal(
                log_date=date.today() - timedelta(days=1),
                food="Yesterday's meal",
                calories=999,
                protein_g=99,
                carbs_g=99,
                fat_g=99,
            )
        )
        db.commit()
    page = client.get("/meals")
    assert page.status_code == 200
    assert "Today's total: 150 kcal" in page.text
    assert "Protein: 20 g" in page.text
    assert "Carbs: 14 g" in page.text
    assert "Fat: 0.7 g" in page.text
    assert "Meals log" not in page.text

    with test_session() as db:
        meal = db.query(Meal).filter(Meal.food == "Skyr").one()
        assert meal.calories == 120
        assert meal.protein_g == 17


@pytest.mark.parametrize("amount_ml", ["250", "375"])
def test_water_intake_adds_to_daily_total(app_client, amount_ml):
    client, test_session = app_client

    response = client.post(
        "/water",
        data={"amount_ml": amount_ml, "log_date": "2026-10-03"},
    )

    assert response.status_code == 303
    with test_session() as db:
        intake = db.query(WaterIntake).one()
        assert intake.amount_ml == int(amount_ml)
        assert intake.log_date == date(2026, 10, 3)
    total = client.get("/water/total", params={"log_date": "2026-10-03"})
    assert total.json() == {"total_ml": int(amount_ml)}


def test_water_total_is_calculated_for_requested_local_date(app_client):
    client, test_session = app_client
    with test_session() as db:
        db.add_all(
            [
                WaterIntake(log_date=date(2026, 10, 2), amount_ml=100),
                WaterIntake(log_date=date(2026, 10, 3), amount_ml=250),
            ]
        )
        db.commit()

    response = client.get("/water/total", params={"log_date": "2026-10-03"})

    assert response.status_code == 200
    assert response.json() == {"total_ml": 250}


def test_water_intake_rejects_nonpositive_amount(app_client):
    client, test_session = app_client

    response = client.post(
        "/water",
        data={"amount_ml": "0", "log_date": date.today().isoformat()},
    )

    assert response.status_code == 400
    assert response.text == "Amount must be greater than 0 ml."
    with test_session() as db:
        assert db.query(WaterIntake).count() == 0


def test_water_intake_can_be_edited_and_deleted(app_client):
    client, test_session = app_client
    with test_session() as db:
        intake = WaterIntake(log_date=date.today(), amount_ml=250)
        db.add(intake)
        db.commit()
        water_id = intake.id

    response = client.post(
        f"/water/{water_id}/edit",
        data={"amount_ml": "500", "log_date": "2026-10-01"},
    )

    assert response.status_code == 303
    total = client.get("/water/total", params={"log_date": date.today().isoformat()})
    assert total.json() == {"total_ml": 0}
    with test_session() as db:
        intake = db.get(WaterIntake, water_id)
        assert intake.amount_ml == 500
        assert intake.log_date == date(2026, 10, 1)

    response = client.post(f"/water/{water_id}/delete")

    assert response.status_code == 303
    with test_session() as db:
        assert db.get(WaterIntake, water_id) is None


def test_meal_and_water_logs_are_hidden_without_deleting_entries(app_client):
    client, test_session = app_client
    with test_session() as db:
        db.add(Meal(log_date=date.today(), food="Saved meal", calories=300))
        db.add(WaterIntake(log_date=date.today(), amount_ml=250))
        db.commit()

    page = client.get("/meals")

    assert page.status_code == 200
    assert "Meals log" not in page.text
    assert "Water log" not in page.text
    assert "<table" not in page.text
    with test_session() as db:
        assert db.query(Meal).count() == 1
        assert db.query(WaterIntake).count() == 1


def test_invalid_water_edit_preserves_existing_amount(app_client):
    client, test_session = app_client
    with test_session() as db:
        intake = WaterIntake(log_date=date.today(), amount_ml=250)
        db.add(intake)
        db.commit()
        water_id = intake.id

    response = client.post(
        f"/water/{water_id}/edit",
        data={"amount_ml": "0"},
    )

    assert response.status_code == 400
    with test_session() as db:
        assert db.get(WaterIntake, water_id).amount_ml == 250


def test_meal_can_be_edited(app_client):
    client, test_session = app_client
    with test_session() as db:
        meal = Meal(
            log_date=date.today(),
            food="Skyr",
            calories=120,
            protein_g=17,
            carbs_g=8,
            fat_g=0.5,
        )
        db.add(meal)
        db.commit()
        meal_id = meal.id

    response = client.post(
        f"/meals/{meal_id}/edit",
        data={
            "food": "Greek yogurt",
            "calories": "150",
            "protein_g": "20",
            "carbs_g": "10",
            "fat_g": "1",
            "log_date": date.today().isoformat(),
            "notes": "Updated",
        },
    )

    assert response.status_code == 303
    page = client.get("/meals")
    assert "Today's total: 150 kcal" in page.text
    with test_session() as db:
        meal = db.get(Meal, meal_id)
        assert meal.food == "Greek yogurt"
        assert meal.calories == 150
        assert meal.protein_g == 20
        assert meal.carbs_g == 10
        assert meal.fat_g == 1
        assert meal.notes == "Updated"


def test_invalid_meal_edit_preserves_entry(app_client):
    client, test_session = app_client
    with test_session() as db:
        meal = Meal(
            log_date=date.today(),
            food="Skyr",
            calories=120,
            protein_g=17,
            carbs_g=8,
            fat_g=0.5,
        )
        db.add(meal)
        db.commit()
        meal_id = meal.id

    response = client.post(
        f"/meals/{meal_id}/edit",
        data={
            "food": "Updated food",
            "calories": "0",
            "protein_g": "20",
            "carbs_g": "10",
            "fat_g": "1",
            "log_date": date.today().isoformat(),
        },
    )

    assert response.status_code == 400
    with test_session() as db:
        meal = db.get(Meal, meal_id)
        assert meal.food == "Skyr"
        assert meal.calories == 120


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