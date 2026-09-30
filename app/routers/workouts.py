from datetime import date

from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Workout

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def parse_required_number(value: str, label: str, parser):
    if not value.strip():
        raise ValueError(f"{label} is required.")
    try:
        return parser(value)
    except ValueError as error:
        raise ValueError(f"{label} must be a valid number.") from error


@router.get("/workouts", response_class=HTMLResponse)
def list_workouts(request: Request, db: Session = Depends(get_db)):
    entries = (
        db.query(Workout)
        .order_by(Workout.log_date.desc(), Workout.id.desc())
        .limit(50)
        .all()
    )
    return templates.TemplateResponse(
        "workouts.html", {
            "request": request,
            "entries": entries,
            "today": date.today(),
            "active": "workouts",
            "form": {},
        }
    )


@router.post("/workouts")
def add_workout(
    request: Request,
    exercise: str = Form(...),
    sets: str = Form(""),
    reps: str = Form(""),
    weight_kg: str = Form(""),
    log_date: date = Form(...),
    notes: str = Form(""),
    db: Session = Depends(get_db),
):
    try:
        sets_value = parse_required_number(sets, "Sets", int)
        reps_value = parse_required_number(reps, "Reps", int)
        weight_value = parse_required_number(weight_kg, "Weight", float)
    except ValueError as error:
        entries = (
            db.query(Workout)
            .order_by(Workout.log_date.desc(), Workout.id.desc())
            .limit(50)
            .all()
        )
        return templates.TemplateResponse(
            "workouts.html",
            {
                "request": request,
                "entries": entries,
                "today": date.today(),
                "active": "workouts",
                "error": str(error),
                "form": {
                    "exercise": exercise,
                    "sets": sets,
                    "reps": reps,
                    "weight_kg": weight_kg,
                    "notes": notes,
                },
            },
            status_code=400,
        )
    entry = Workout(
        exercise=exercise, sets=sets_value, reps=reps_value,
        weight_kg=weight_value, log_date=log_date, notes=notes,
    )
    db.add(entry)
    db.commit()
    return RedirectResponse(url="/workouts", status_code=303)


@router.post("/workouts/{workout_id}/delete")
def delete_workout(workout_id: int, db: Session = Depends(get_db)):
    db.query(Workout).filter(Workout.id == workout_id).delete()
    db.commit()
    return RedirectResponse(url="/workouts", status_code=303)
