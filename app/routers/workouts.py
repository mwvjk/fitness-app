from datetime import date

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Workout
from app.validation import parse_required_number

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def get_workouts(db: Session):
    return (
        db.query(Workout)
        .order_by(Workout.log_date.desc(), Workout.id.desc())
        .limit(50)
        .all()
    )


def render_workouts(request: Request, db: Session, status_code: int = 200, **context):
    return templates.TemplateResponse(
        "workouts.html",
        {
            "request": request,
            "entries": get_workouts(db),
            "today": date.today(),
            "active": "workouts",
            "form": {},
            **context,
        },
        status_code=status_code,
    )


@router.get("/workouts", response_class=HTMLResponse)
def list_workouts(request: Request, db: Session = Depends(get_db)):
    return render_workouts(request, db)


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
        return render_workouts(
            request,
            db,
            status_code=400,
            error=str(error),
            form={
                "exercise": exercise,
                "sets": sets,
                "reps": reps,
                "weight_kg": weight_kg,
                "notes": notes,
            },
        )
    entry = Workout(
        exercise=exercise, sets=sets_value, reps=reps_value,
        weight_kg=weight_value, log_date=log_date, notes=notes,
    )
    db.add(entry)
    db.commit()
    return RedirectResponse(url="/workouts", status_code=303)


@router.post("/workouts/{workout_id}/edit")
def edit_workout(
    workout_id: int,
    request: Request,
    exercise: str = Form(""),
    sets: str = Form(""),
    reps: str = Form(""),
    weight_kg: str = Form(""),
    log_date: str = Form(""),
    notes: str = Form(""),
    db: Session = Depends(get_db),
):
    entry = db.get(Workout, workout_id)
    if entry is None:
        return HTMLResponse("Workout not found.", status_code=404)

    values = {
        "exercise": exercise,
        "sets": sets,
        "reps": reps,
        "weight_kg": weight_kg,
        "log_date": log_date,
        "notes": notes,
    }
    try:
        if not exercise.strip():
            raise ValueError("Exercise is required.")
        if not log_date.strip():
            raise ValueError("Date is required.")
        log_date_value = date.fromisoformat(log_date)
        sets_value = parse_required_number(sets, "Sets", int)
        reps_value = parse_required_number(reps, "Reps", int)
        weight_value = parse_required_number(weight_kg, "Weight", float)
    except ValueError as error:
        return render_workouts(
            request,
            db,
            status_code=400,
            edit_entry_id=workout_id,
            edit_values=values,
            edit_error=str(error),
        )

    entry.exercise = exercise.strip()
    entry.sets = sets_value
    entry.reps = reps_value
    entry.weight_kg = weight_value
    entry.log_date = log_date_value
    entry.notes = notes
    db.commit()
    return RedirectResponse(url="/workouts", status_code=303)


@router.post("/workouts/{workout_id}/delete")
def delete_workout(workout_id: int, db: Session = Depends(get_db)):
    db.query(Workout).filter(Workout.id == workout_id).delete()
    db.commit()
    return RedirectResponse(url="/workouts", status_code=303)
