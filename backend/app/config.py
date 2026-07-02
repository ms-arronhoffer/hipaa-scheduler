"""Application settings loaded from environment variables.

Pydantic BaseSettings validates env vars on process start. No defaults for
secrets (JWT_SECRET, POSTGRES_PASSWORD, DEFAULT_ADMIN_PASSWORD) — the app
refuses to boot without them.
"""
from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")

    # Core
    app_env: Literal["development", "staging", "production"] = "development"
    log_level: str = "INFO"
    log_format: Literal["json", "text"] = "json"
    frontend_url: str = "https://localhost"
    admin_url: str = "https://localhost:4001"
    patient_url: str = "https://localhost:4002"

    # Database
    database_url: str

    # Auth (secrets — no defaults)
    jwt_secret: SecretStr
    jwt_issuer: str = "hipaa-scheduler"
    jwt_access_ttl_min: int = 15
    jwt_refresh_ttl_days: int = 7
    session_idle_min: int = 15
    mfa_required_default: bool = True

    # Admin bootstrap
    default_admin_email: str = "admin@example.com"
    default_admin_password: SecretStr
    super_admin_emails: str = ""  # comma-separated

    # Rate limiting
    rate_limit_default: str = "100/minute"
    rate_limit_auth: str = "10/minute"
    rate_limit_public_booking: str = "30/minute"

    # HIPAA
    phi_audit_enabled: bool = True
    retention_years: int = 6
    # Application-layer encryption key for ePHI at rest (secret — no default).
    # Dedicated key, NOT reused from jwt_secret, so the two can rotate
    # independently. May be a comma-separated list for key rotation: the first
    # entry encrypts, all entries are accepted for decryption. See
    # app/utils/crypto.py.
    phi_encryption_key: SecretStr

    # Notifications
    sendgrid_api_key: SecretStr | None = None
    email_from: str = "noreply@example.com"
    email_from_name: str = "Practice Scheduler"
    twilio_sid: str | None = None
    twilio_token: SecretStr | None = None
    twilio_from: str | None = None

    # Object storage
    s3_endpoint: str | None = None
    s3_bucket: str | None = None
    s3_access_key: str | None = None
    s3_secret_key: SecretStr | None = None
    s3_region: str | None = None

    # Calendar OAuth
    google_oauth_id: str | None = None
    google_oauth_secret: SecretStr | None = None
    ms_oauth_id: str | None = None
    ms_oauth_secret: SecretStr | None = None

    # Webhooks
    webhook_hmac_alg: str = "sha256"
    webhook_timeout_sec: int = 5
    webhook_max_attempts: int = 6

    # Observability
    sentry_dsn: str | None = None

    @computed_field  # type: ignore[misc]
    @property
    def super_admin_email_list(self) -> list[str]:
        return [e.strip().lower() for e in self.super_admin_emails.split(",") if e.strip()]

    @computed_field  # type: ignore[misc]
    @property
    def cors_origins(self) -> list[str]:
        return [self.frontend_url, self.admin_url, self.patient_url]


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]


settings = get_settings()
