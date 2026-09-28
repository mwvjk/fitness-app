from datetime import date

from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Workout

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/workouts", response_class=HTMLResponse)
def list_workouts(request: Request, db: Session = Depends(get_db)):
    entries = (
        db.query(Workout)
        .order_by(Workout.log_date.desc(), Workout.id.desc())
        .limit(50)
        .all()
    )
    return templates.TemplateResponse(
        "workouts.html", {"request": request, "entries": entries, "today": date.today(), "active": "workouts"}
    )


@router.post("/workouts")
def add_workout(
    exercise: str = Form(...),
    sets: int = Form(None),
    reps: int = Form(None),
    weight_kg: float = Form(None),
    log_date: date = Form(...),
    notes: str = Form(""),
    db: Session = Depends(get_db),
):
    entry = Workout(
        exercise=exercise, sets=sets, reps=reps,
        weight_kg=weight_kg, log_date=log_date, notes=notes,
    )
    db.add(entry)
    db.commit()
    return RedirectResponse(url="/workouts", status_code=303)


@router.post("/workouts/{workout_id}/delete")
def delete_workout(workout_id: int, db: Session = Depends(get_db)):
    db.query(Workout).filter(Workout.id == workout_id).delete()
    db.commit()
    return RedirectResponse(url="/workouts", status_code=303)
