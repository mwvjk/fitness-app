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


def parse_required_number(value: str, label: str, parser):
    if not value.strip():
        raise ValueError(f"{label} is required.")
    try:
        return parser(value)
    except ValueError as error:
        raise ValueError(f"{label} must be a valid number.") from error


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
        {
            "request": request,
            "entries": entries,
            "today": today,
            "today_total": today_total,
            "active": "meals",
            "form": {},
        },
    )


@router.post("/meals")
def add_meal(
    request: Request,
    food: str = Form(""),
    calories: str = Form(""),
    protein_g: str = Form(""),
    carbs_g: str = Form(""),
    fat_g: str = Form(""),
    log_date: str = Form(""),
    notes: str = Form(""),
    db: Session = Depends(get_db),
):
    try:
        if not food.strip():
            raise ValueError("Food is required.")
        if not log_date.strip():
            raise ValueError("Date is required.")
        try:
            log_date_value = date.fromisoformat(log_date)
        except ValueError as error:
            raise ValueError("Date must be a valid date.") from error
        calories_value = parse_required_number(calories, "Calories", int)
        protein_value = parse_required_number(protein_g, "Protein", float)
        carbs_value = parse_required_number(carbs_g, "Carbs", float)
        fat_value = parse_required_number(fat_g, "Fat", float)
    except ValueError as error:
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
            {
                "request": request,
                "entries": entries,
                "today": today,
                "today_total": today_total,
                "active": "meals",
                "error": str(error),
                "form": {
                    "food": food,
                    "calories": calories,
                    "protein_g": protein_g,
                    "carbs_g": carbs_g,
                    "fat_g": fat_g,
                    "notes": notes,
                },
            },
            status_code=400,
        )
    entry = Meal(
        food=food.strip(), calories=calories_value, protein_g=protein_value,
        carbs_g=carbs_value, fat_g=fat_value, log_date=log_date_value, notes=notes,
    )
    db.add(entry)
    db.commit()
    return RedirectResponse(url="/meals", status_code=303)


@router.post("/meals/{meal_id}/delete")
def delete_meal(meal_id: int, db: Session = Depends(get_db)):
    db.query(Meal).filter(Meal.id == meal_id).delete()
    db.commit()
    return RedirectResponse(url="/meals", status_code=303)
