from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from app.database import Base, engine
from app.routers.workouts import router as workouts_router
from app.routers.meals import router as meals_router

# Create tables on startup if they don't exist yet.
# For anything beyond this simple schema, switch to Alembic migrations.
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Fitness App")

app.include_router(workouts_router)
app.include_router(meals_router)


@app.get("/")
def home():
    return RedirectResponse(url="/workouts")


@app.get("/healthz")
def healthz():
    return {"status": "ok"}
