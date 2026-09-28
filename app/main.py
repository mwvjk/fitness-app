from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from app.database import Base, engine
from app.routers.workouts import router as workouts_router
from app.routers.meals import router as meals_router

# Catch database connection errors gracefully during startup
try:
    Base.metadata.create_all(bind=engine)
except Exception as e:
    print(f"Skipping database init: {e}")

app = FastAPI(title="Fitness App")

app.include_router(workouts_router)
app.include_router(meals_router)


@app.get("/")
def home():
    return RedirectResponse(url="/workouts")


@app.get("/healthz")
def healthz():
    return {"status": "ok"}
