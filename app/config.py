from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql://fitness-app:fitness-app@localhost:5432/fitness-app"

    class Config:
        env_file = ".env"


settings = Settings()
