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
    # Run `alembic upgrade head` on backend startup (start.py) so a freshly
    # provisioned stack has its schema before the app serves. Disable to manage
    # migrations out-of-band.
    run_migrations_on_startup: bool = True

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
    # OAuth redirect (callback) URIs registered with each provider. When unset
    # they are derived from `frontend_url` + the callback route. They MUST be
    # publicly reachable and match the provider console's allow-list exactly.
    google_oauth_redirect_uri: str | None = None
    ms_oauth_redirect_uri: str | None = None
    # After a successful OAuth callback the browser is redirected here (staff
    # calendar-settings page). `?calendar=<connected|error>` is appended.
    calendar_oauth_success_path: str = "/settings/integrations"
    # Forward window (days) the reconcile pass mirrors appointments into the
    # connected calendar. Past events and events beyond the window are ignored.
    calendar_sync_window_days: int = 30

    # Webhooks
    webhook_hmac_alg: str = "sha256"
    webhook_timeout_sec: int = 5
    webhook_max_attempts: int = 6

    # Notification delivery retry (email/SMS). A failed send is re-attempted by
    # the notification retry sweep with the backoff schedule below (minutes);
    # once `notification_max_attempts` is reached the row stays `failed`.
    notification_max_attempts: int = 4
    notification_retry_delays_min: list[int] = [1, 5, 30, 120]

    # Observability
    sentry_dsn: str | None = None

    # Background worker liveness. The worker writes a heartbeat file after each
    # scheduler tick; the API `/worker/health` probe reads it and reports stale
    # if it hasn't been updated within `worker_heartbeat_max_age_sec`.
    worker_heartbeat_path: str = "/tmp/hs_worker_heartbeat.json"
    worker_heartbeat_max_age_sec: int = 900

    # Password policy & lifecycle
    password_min_length: int = 12
    password_expiry_days: int = 90  # 0 disables expiry
    password_history_depth: int = 5  # remembered hashes to block reuse; 0 disables
    password_hibp_enabled: bool = True  # k-anonymity breach check (pwnedpasswords.com)
    password_reset_ttl_min: int = 30

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
