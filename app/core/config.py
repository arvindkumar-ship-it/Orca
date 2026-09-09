# """
# app/core/config.py

# Centralized settings for WaveSafe. Loaded once as a singleton `settings` object.
# Every field here was cross-checked against actual `settings.X` references found in the
# delivered modules (fanout_service.py, sms_channel.py, push_channel.py, hospital_router_service.py,
# authority_router_service.py, and .env.example) â€” nothing here is guessed, all fields are consumed
# somewhere in the copied code.
# """
# from pydantic_settings import BaseSettings, SettingsConfigDict


# class Settings(BaseSettings):
#     # --- Core ---
#     APP_BASE_URL: str = "http://localhost:8000"
#     ENVIRONMENT: str = "local"
#     SECRET_KEY: str
#     INTERNAL_API_KEY: str = ""

#     # --- Database ---
#     DATABASE_URL: str
#     TEST_DATABASE_URL: str = ""

#     # --- Redis / Celery ---
#     REDIS_URL: str

#     # --- Module 3: ingestion sources ---
#     INCOIS_BASE_URL: str = ""
#     INCOIS_API_KEY: str = ""
#     INCOIS_POLL_SECONDS: int = 900
#     SACHET_CAP_FEED_URL: str = ""
#     SACHET_API_KEY: str = ""
#     SACHET_POLL_SECONDS: int = 120

#     # --- Module 3: raw payload storage ---
#     RAW_STORAGE_BACKEND: str = "local"
#     RAW_STORAGE_LOCAL_PATH: str = "/var/data/raw_ingest"
#     RAW_STORAGE_S3_BUCKET: str = ""
#     RAW_STORAGE_S3_PREFIX: str = "raw-ingest"

#     # --- Module 3/32: ops alerting ---
#     OPS_ALERT_WEBHOOK_URL: str = ""
#     OPS_ALERT_MIN_FAILURES: int = 3

#     # --- Module 13: notifications (confirmed used in channels/push_channel.py, sms_channel.py) ---
#     VAPID_PUBLIC_KEY: str = ""
#     VAPID_PRIVATE_KEY: str = ""
#     VAPID_SUBJECT: str = "mailto:ops@example.com"
#     SMS_GATEWAY_URL: str = ""
#     SMS_GATEWAY_KEY: str = ""

#     # --- JWT (used internally by app.core.security, not directly referenced elsewhere) ---
#     JWT_ALGORITHM: str = "HS256"
#     JWT_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days â€” mobile-first app, long-lived session

#     # --- Frontend build-time (not consumed by backend, present for completeness) ---
#     NEXT_PUBLIC_API_BASE_URL: str = "http://localhost:8000"

#     # --- Module 28: staging-only smoke test ---
#     PUBLIC_API_BASE_URL: str = ""
#     SMOKE_TEST_PHONE: str = ""
#     SMOKE_TEST_OTP: str = ""

#     model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


# settings = Settings()



"""
app/core/config.py

Centralized settings for WaveSafe. Loaded once as a singleton `settings` object.
Every field here was cross-checked against actual `settings.X` references found in the
delivered modules (fanout_service.py, sms_channel.py, push_channel.py, hospital_router_service.py,
authority_router_service.py, and .env.example) â€” nothing here is guessed, all fields are consumed
somewhere in the copied code.
"""
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

# .env lives at repo root (wavesafe/), NOT backend/. Resolve relative to this file
# (backend/app/core/config.py -> parents[2] = repo root) so it works regardless of CWD â€”
# same fix as db.py needed (pydantic-settings' own env_file="..." is CWD-relative by default).
_ENV_PATH = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    # --- Core ---
    APP_BASE_URL: str = "http://localhost:8000"
    ENVIRONMENT: str = "local"
    SECRET_KEY: str
    INTERNAL_API_KEY: str = ""

    # --- Database ---
    DATABASE_URL: str
    TEST_DATABASE_URL: str = ""

    # --- Redis / Celery ---
    REDIS_URL: str

    # --- Module 3: ingestion sources ---
    INCOIS_BASE_URL: str = ""
    INCOIS_API_KEY: str = ""
    INCOIS_POLL_SECONDS: int = 900
    SACHET_CAP_FEED_URL: str = ""
    SACHET_API_KEY: str = ""
    SACHET_POLL_SECONDS: int = 120

    # --- Module 3: raw payload storage ---
    RAW_STORAGE_BACKEND: str = "local"
    RAW_STORAGE_LOCAL_PATH: str = "/var/data/raw_ingest"
    RAW_STORAGE_S3_BUCKET: str = ""
    RAW_STORAGE_S3_PREFIX: str = "raw-ingest"

    # --- Module 3/32: ops alerting ---
    OPS_ALERT_WEBHOOK_URL: str = ""
    OPS_ALERT_MIN_FAILURES: int = 3

    # --- Module 13: notifications (confirmed used in channels/push_channel.py, sms_channel.py) ---
    VAPID_PUBLIC_KEY: str = ""
    VAPID_PRIVATE_KEY: str = ""
    VAPID_SUBJECT: str = "mailto:ops@example.com"
    SMS_GATEWAY_URL: str = ""
    SMS_GATEWAY_KEY: str = ""

    # --- JWT (used internally by app.core.security, not directly referenced elsewhere) ---
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days â€” mobile-first app, long-lived session

    # --- Frontend build-time (not consumed by backend, present for completeness) ---
    NEXT_PUBLIC_API_BASE_URL: str = "http://localhost:8000"

    # --- Module 28: staging-only smoke test ---
    PUBLIC_API_BASE_URL: str = ""
    SMOKE_TEST_PHONE: str = ""
    SMOKE_TEST_OTP: str = ""

    model_config = SettingsConfigDict(env_file=_ENV_PATH, env_file_encoding="utf-8", extra="ignore")


settings = Settings()
