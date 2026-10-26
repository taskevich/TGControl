from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.application.policies import Policies
from app.infrastructure.s3_storage import S3Config
from app.infrastructure.telegram.client import ClientDefaults


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"), env_file_encoding="utf-8", extra="ignore"
    )

    DATABASE_URL: str = (
        "postgresql+asyncpg://tgcontrol:tgcontrol@localhost:5432/tgcontrol"
    )
    REDIS_URL: str = "redis://localhost:6379/0"

    SECRET_KEY: str = "change-me-please"

    SESSION_ENCRYPTION_KEY: str = ""
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 720
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = "admin"
    LOGIN_MAX_ATTEMPTS: int = 10
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"

    TG_API_ID: int = 0
    TG_API_HASH: str = ""
    TG_DEVICE_MODEL: str = "PC 64bit"
    TG_SYSTEM_VERSION: str = "Windows 10"
    TG_APP_VERSION: str = "5.6.3 x64"
    TG_LANG_CODE: str = "ru"
    TG_SYSTEM_LANG_CODE: str = "ru-RU"

    BULK_DELAY_MIN: float = 3.0
    BULK_DELAY_MAX: float = 8.0
    BULK_CONCURRENCY: int = 3
    FLOOD_WAIT_MAX: int = 120

    STATS_REFRESH_MINUTES: int = 30
    STATS_REFRESH_DAYS: int = 7

    MESSAGES_SYNC_MINUTES: int = 0
    MESSAGES_SYNC_DIALOGS: int = 50

    S3_BUCKET: str = ""
    S3_ENDPOINT_URL: str = ""
    S3_REGION: str = "us-east-1"
    S3_ACCESS_KEY: str = ""
    S3_SECRET_KEY: str = ""
    S3_PREFIX: str = ""
    MEDIA_MAX_SIZE_MB: int = 1024
    MEDIA_CONCURRENCY: int = 2
    MEDIA_TMP_DIR: str = ""

    @field_validator(
        "TG_API_ID",
        "STATS_REFRESH_MINUTES",
        "STATS_REFRESH_DAYS",
        "BULK_CONCURRENCY",
        "MESSAGES_SYNC_MINUTES",
        "MESSAGES_SYNC_DIALOGS",
        "MEDIA_MAX_SIZE_MB",
        "MEDIA_CONCURRENCY",
        mode="before",
    )
    @classmethod
    def empty_int(cls, v):
        return 0 if v in ("", None) else v

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    def s3_config(self) -> S3Config | None:
        if not self.S3_BUCKET:
            return None
        return S3Config(
            bucket=self.S3_BUCKET,
            endpoint_url=self.S3_ENDPOINT_URL or None,
            region=self.S3_REGION or "us-east-1",
            access_key=self.S3_ACCESS_KEY or None,
            secret_key=self.S3_SECRET_KEY or None,
            prefix=self.S3_PREFIX,
        )

    def policies(self) -> Policies:
        return Policies(
            login_max_attempts=self.LOGIN_MAX_ATTEMPTS,
            bulk_delay_min=self.BULK_DELAY_MIN,
            bulk_delay_max=self.BULK_DELAY_MAX,
            bulk_concurrency=self.BULK_CONCURRENCY,
            flood_wait_max=self.FLOOD_WAIT_MAX,
            stats_refresh_minutes=self.STATS_REFRESH_MINUTES,
            stats_refresh_days=self.STATS_REFRESH_DAYS,
            messages_sync_minutes=self.MESSAGES_SYNC_MINUTES,
            messages_sync_dialogs=self.MESSAGES_SYNC_DIALOGS,
            media_max_size=self.MEDIA_MAX_SIZE_MB * 2**20,
            media_concurrency=self.MEDIA_CONCURRENCY,
        )

    def client_defaults(self) -> ClientDefaults:
        return ClientDefaults(
            api_id=self.TG_API_ID,
            api_hash=self.TG_API_HASH,
            device_model=self.TG_DEVICE_MODEL,
            system_version=self.TG_SYSTEM_VERSION,
            app_version=self.TG_APP_VERSION,
            lang_code=self.TG_LANG_CODE,
            system_lang_code=self.TG_SYSTEM_LANG_CODE,
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
