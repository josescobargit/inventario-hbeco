from functools import lru_cache
from typing import Optional
from urllib.parse import quote

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Inventario Operativo"
    environment: str = "local"
    database_url: str = "postgresql+psycopg://inventario:inventario@localhost:5432/inventario"
    migration_database_url: Optional[str] = None
    database_password: Optional[SecretStr] = None
    database_connect_timeout_seconds: int = 10
    database_pool_timeout_seconds: int = 15
    database_pool_recycle_seconds: int = 300
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    session_cookie_name: str = "inventory_session"
    session_hours: int = 12
    login_max_attempts: int = 5
    login_lock_minutes: int = 15
    cookie_secure: bool = False

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    def _resolved_database_url(self, url: str) -> str:
        if "{password}" not in url:
            return url
        if self.database_password is None:
            raise ValueError("DATABASE_PASSWORD is required when a database URL uses {password}.")
        encoded_password = quote(self.database_password.get_secret_value(), safe="")
        return url.replace("{password}", encoded_password)

    @property
    def effective_database_url(self) -> str:
        return self._resolved_database_url(self.database_url)

    @property
    def effective_migration_database_url(self) -> str:
        url = self.migration_database_url or self.database_url
        return self._resolved_database_url(url)


@lru_cache
def get_settings() -> Settings:
    return Settings()
