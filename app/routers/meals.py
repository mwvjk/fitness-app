from datetime import date

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Meal, WaterIntake
from app.validation import parse_required_number

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def get_daily_meal_totals(db: Session, log_date: date):
    calories, protein, carbs, fat = (
        db.query(
            func.coalesce(func.sum(Meal.calories), 0),
            func.coalesce(func.sum(Meal.protein_g), 0),
            func.coalesce(func.sum(Meal.carbs_g), 0),
            func.coalesce(func.sum(Meal.fat_g), 0),
        )
        .filter(Meal.log_date == log_date)
        .one()
    )
    return {
        "today_total": calories,
        "today_protein": round(protein, 1),
        "today_carbs": round(carbs, 1),
        "today_fat": round(fat, 1),
    }


def render_meals(request: Request, db: Session, status_code: int = 200, **context):
    today = date.today()
    return templates.TemplateResponse(
        "meals.html",
        {
            "request": request,
            "today": today,
            **get_daily_meal_totals(db, today),
            "active": "meals",
            "form": {},
            **context,
        },
        status_code=status_code,
    )


@router.get("/water/total")
def get_water_total(log_date: date, db: Session = Depends(get_db)):
    total = (
        db.query(func.coalesce(func.sum(WaterIntake.amount_ml), 0))
        .filter(WaterIntake.log_date == log_date)
        .scalar()
    )
    return {"total_ml": total}


@router.post("/water/total")
def set_water_total(
    total_ml: str = Form(""),
    log_date: str = Form(""),
    db: Session = Depends(get_db),
):
    try:
        total = parse_required_number(total_ml, "Total", int)
        if total < 0:
            raise ValueError("Total must be 0 ml or greater.")
        if not log_date.strip():
            raise ValueError("Date is required.")
        total_date = date.fromisoformat(log_date)
    except ValueError as error:
        return PlainTextResponse(str(error), status_code=400)

    entries = (
        db.query(WaterIntake)
        .filter(WaterIntake.log_date == total_date)
        .order_by(WaterIntake.id.desc())
        .all()
    )
    difference = total - sum(entry.amount_ml for entry in entries)
    if difference > 0:
        if entries:
            entries[0].amount_ml += difference
        else:
            db.add(WaterIntake(log_date=total_date, amount_ml=total))
    elif difference < 0:
        remaining = -difference
        for entry in entries:
            reduction = min(entry.amount_ml, remaining)
            entry.amount_ml -= reduction
            remaining -= reduction
            if not remaining:
                break

    db.commit()
    return RedirectResponse(url="/meals", status_code=303)


@router.get("/meals", response_class=HTMLResponse)
def list_meals(request: Request, db: Session = Depends(get_db)):
    return render_meals(request, db)


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
        if calories_value == 0 and any(
            value > 0 for value in (protein_value, carbs_value, fat_value)
        ):
            raise ValueError("Calories must be greater than 0 when macros are entered.")
    except ValueError as error:
        return render_meals(
            request,
            db,
            status_code=400,
            error=str(error),
            form={
                "food": food,
                "calories": calories,
                "protein_g": protein_g,
                "carbs_g": carbs_g,
                "fat_g": fat_g,
                "notes": notes,
            },
        )
    entry = Meal(
        food=food.strip(), calories=calories_value, protein_g=protein_value,
        carbs_g=carbs_value, fat_g=fat_value, log_date=log_date_value, notes=notes,
    )
    db.add(entry)
    db.commit()
    return RedirectResponse(url="/meals", status_code=303)


@router.post("/water")
def add_water(
    amount_ml: str = Form(""),
    log_date: str = Form(""),
    db: Session = Depends(get_db),
):
    try:
        amount = parse_required_number(amount_ml, "Amount", int)
        if amount <= 0:
            raise ValueError("Amount must be greater than 0 ml.")
        if not log_date.strip():
            raise ValueError("Date is required.")
        log_date_value = date.fromisoformat(log_date)
    except ValueError as error:
        return PlainTextResponse(str(error), status_code=400)

    db.add(WaterIntake(log_date=log_date_value, amount_ml=amount))
    db.commit()
    return RedirectResponse(url="/meals", status_code=303)


@router.post("/water/{water_id}/edit")
def edit_water(
    water_id: int,
    amount_ml: str = Form(""),
    log_date: str | None = Form(None),
    db: Session = Depends(get_db),
):
    entry = db.get(WaterIntake, water_id)
    if entry is None:
        return PlainTextResponse("Water entry not found.", status_code=404)
    try:
        amount = parse_required_number(amount_ml, "Amount", int)
        if amount <= 0:
            raise ValueError("Amount must be greater than 0 ml.")
        if log_date is not None:
            log_date_value = date.fromisoformat(log_date)
        else:
            log_date_value = entry.log_date
    except ValueError as error:
        return PlainTextResponse(str(error), status_code=400)

    entry.amount_ml = amount
    entry.log_date = log_date_value
    db.commit()
    return RedirectResponse(url="/meals", status_code=303)


@router.post("/water/{water_id}/delete")
def delete_water(water_id: int, db: Session = Depends(get_db)):
    entry = db.get(WaterIntake, water_id)
    if entry is None:
        return PlainTextResponse("Water entry not found.", status_code=404)
    db.delete(entry)
    db.commit()
    return RedirectResponse(url="/meals", status_code=303)


@router.post("/meals/{meal_id}/edit")
def edit_meal(
    meal_id: int,
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
    entry = db.get(Meal, meal_id)
    if entry is None:
        return HTMLResponse("Meal not found.", status_code=404)

    values = {
        "food": food,
        "calories": calories,
        "protein_g": protein_g,
        "carbs_g": carbs_g,
        "fat_g": fat_g,
        "log_date": log_date,
        "notes": notes,
    }
    try:
        if not food.strip():
            raise ValueError("Food is required.")
        if not log_date.strip():
            raise ValueError("Date is required.")
        log_date_value = date.fromisoformat(log_date)
        calories_value = parse_required_number(calories, "Calories", int)
        protein_value = parse_required_number(protein_g, "Protein", float)
        carbs_value = parse_required_number(carbs_g, "Carbs", float)
        fat_value = parse_required_number(fat_g, "Fat", float)
        if calories_value == 0 and any(
            value > 0 for value in (protein_value, carbs_value, fat_value)
        ):
            raise ValueError("Calories must be greater than 0 when macros are entered.")
    except ValueError as error:
        return render_meals(
            request,
            db,
            status_code=400,
            edit_entry_id=meal_id,
            edit_values=values,
            edit_error=str(error),
        )

    entry.food = food.strip()
    entry.calories = calories_value
    entry.protein_g = protein_value
    entry.carbs_g = carbs_value
    entry.fat_g = fat_value
    entry.log_date = log_date_value
    entry.notes = notes
    db.commit()
    return RedirectResponse(url="/meals", status_code=303)


@router.post("/meals/{meal_id}/delete")
def delete_meal(meal_id: int, db: Session = Depends(get_db)):
    db.query(Meal).filter(Meal.id == meal_id).delete()
    db.commit()
    return RedirectResponse(url="/meals", status_code=303)
