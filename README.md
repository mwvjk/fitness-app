# Fitness App

A small self-hosted app for logging workouts, meals, and water.

## Run with Docker

Build the image:

```sh
docker build -t fitness-app .
```

Run without persistent storage for a quick test:

```sh
docker run --rm -p 8000:8000 \
  -e DATABASE_URL=sqlite:////tmp/fitness.db \
  fitness-app
```

Open <http://localhost:8000>. Data in this test container is temporary and is
lost when the container is removed.

For persistent SQLite storage, mount a volume:

```sh
docker run -d --name fitness-app -p 8000:8000 \
  -e DATABASE_URL=sqlite:////data/fitness.db \
  -v fitness-data:/data \
  --restart unless-stopped \
  fitness-app
```

You can also set `DATABASE_URL` to a PostgreSQL connection URL. The app runs
database migrations when it starts.

## Development

Requires Python 3.12 or later:

```sh
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
export DATABASE_URL=sqlite:///./fitness.db
alembic upgrade head
uvicorn app.main:app --reload
```

Run tests with `pytest`.