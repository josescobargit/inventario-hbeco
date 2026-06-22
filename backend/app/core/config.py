from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Inventario Operativo"
    environment: str = "local"
    database_url: str = "postgresql+psycopg://inventario:inventario@localhost:5432/inventario"
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    session_cookie_name: str = "inventory_session"
    session_hours: int = 12
    login_max_attempts: int = 5
    login_lock_minutes: int = 15
    cookie_secure: bool = False

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()
