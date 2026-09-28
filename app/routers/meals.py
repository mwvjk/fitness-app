from datetime import date

from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models import Meal

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/meals", response_class=HTMLResponse)
def list_meals(request: Request, db: Session = Depends(get_db)):
    today = date.today()
    entries = (
        db.query(Meal)
        .order_by(Meal.log_date.desc(), Meal.id.desc())
        .limit(50)
        .all()
    )
    today_total = (
        db.query(func.coalesce(func.sum(Meal.calories), 0))
        .filter(Meal.log_date == today)
        .scalar()
    )
    return templates.TemplateResponse(
        "meals.html",
        {"request": request, "entries": entries, "today": today, "today_total": today_total, "active": "meals"},
    )


@router.post("/meals")
def add_meal(
    food: str = Form(...),
    calories: int = Form(None),
    protein_g: float = Form(None),
    carbs_g: float = Form(None),
    fat_g: float = Form(None),
    log_date: date = Form(...),
    notes: str = Form(""),
    db: Session = Depends(get_db),
):
    entry = Meal(
        food=food, calories=calories, protein_g=protein_g,
        carbs_g=carbs_g, fat_g=fat_g, log_date=log_date, notes=notes,
    )
    db.add(entry)
    db.commit()
    return RedirectResponse(url="/meals", status_code=303)


@router.post("/meals/{meal_id}/delete")
def delete_meal(meal_id: int, db: Session = Depends(get_db)):
    db.query(Meal).filter(Meal.id == meal_id).delete()
    db.commit()
    return RedirectResponse(url="/meals", status_code=303)
