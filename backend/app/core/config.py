from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    SECRET_KEY: str = "dev-insecure-key-change-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # CORS origins — comma-separated list (NCA ECC 2-5)
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]

    # Account lockout (NCA ECC 2-1)
    MAX_LOGIN_ATTEMPTS: int = 5
    LOCKOUT_MINUTES: int = 15

    # Redis / Celery (Phase 4)
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"

    # SMTP (Phase 5)
    SMTP_HOST: str = "localhost"
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    NOTIFICATION_ENABLED: bool = False

    # File storage (Phase 5)
    FILE_STORAGE_PATH: str = "/tmp/tuwaiq-files"
    FILE_STORAGE_BACKEND: str = "local"  # "local" or "s3"


settings = Settings()  # type: ignore[call-arg]
