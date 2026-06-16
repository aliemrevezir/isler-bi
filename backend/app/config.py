"""Platform yapılandırması. Ortam değişkeninden okunur; geliştirme varsayılanı vardır."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    # --- Platform DB (raw + derived + app şemaları) ---
    APP_PG_URL: str = "postgresql+psycopg2://isler:isler_dev_pwd@localhost:5432/isler"
    APP_REDIS_URL: str = "redis://localhost:6379/0"

    # --- Auth ---
    APP_JWT_SECRET: str = "dev-secret-change-me"
    APP_JWT_ALG: str = "HS256"
    APP_JWT_TTL_MIN: int = 480
    APP_CORS_ORIGINS: str = "http://localhost:8080,http://127.0.0.1:8080,http://localhost:5173"

    # --- Logo / META (MSSQL kaynak) — worker/beat kullanır ---
    LOGO_SERVER: str = "192.168.46.174"
    LOGO_PORT: int = 1433
    LOGO_USER: str = "mert"
    LOGO_PASSWORD: str = ""
    LOGO_DB: str = "LOGO"
    META_DB: str = "META"
    LOGO_PERIOD: str = "01"
    HISTORY_START_YEAR: int = 2023

    # --- Job çalıştırma limiti (Celery soft_time_limit, saniye) ---
    JOB_SOFT_TIME_LIMIT: int = 600
    JOB_TIME_LIMIT: int = 660

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.APP_CORS_ORIGINS.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
