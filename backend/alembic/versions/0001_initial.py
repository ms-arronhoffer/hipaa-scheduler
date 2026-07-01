"""Initial schema.

Revision ID: 0001_initial
Revises:
Create Date: 2026-07-01

Adds every table plus the two GiST exclusion constraints that prevent
overlapping active appointments per provider and per resource.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg


revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def _tstamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    ]


def _soft_delete() -> sa.Column:
    return sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True)


def _pk() -> sa.Column:
    return sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()"))


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")

    op.create_table(
        "organizations",
        _pk(),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(80), nullable=False, unique=True),
        sa.Column("plan", sa.String(30), nullable=False, server_default="starter"),
        sa.Column("seats", sa.Integer, nullable=False, server_default="5"),
        sa.Column("baa_signed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("mfa_required", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("settings", pg.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        *_tstamps(),
        _soft_delete(),
    )

    op.create_table(
        "offices",
        _pk(),
        sa.Column("org_id", pg.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("timezone", sa.String(64), nullable=False, server_default="America/New_York"),
        sa.Column("phone", sa.String(30), nullable=True),
        sa.Column("address", pg.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("hours", pg.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("holidays", pg.JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        *_tstamps(),
        _soft_delete(),
    )

    op.create_table(
        "users",
        _pk(),
        sa.Column("org_id", pg.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("email", sa.String(255), nullable=False, index=True),
        sa.Column("password_hash", sa.String(255), nullable=True),
        sa.Column("first_name", sa.String(80), nullable=True),
        sa.Column("last_name", sa.String(80), nullable=True),
        sa.Column("roles", pg.ARRAY(sa.String(30)), nullable=False, server_default=sa.text("ARRAY[]::varchar[]")),
        sa.Column("is_super_admin", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("totp_secret", sa.String(64), nullable=True),
        sa.Column("mfa_enrolled", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("backup_codes", pg.JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        *_tstamps(),
        _soft_delete(),
        sa.UniqueConstraint("org_id", "email", name="uq_users_org_email"),
    )

    op.create_table(
        "provider_profiles",
        _pk(),
        sa.Column("org_id", pg.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("user_id", pg.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("npi", sa.String(20), nullable=True),
        sa.Column("specialty", sa.String(80), nullable=True),
        sa.Column("default_office_id", pg.UUID(as_uuid=True), sa.ForeignKey("offices.id", ondelete="SET NULL"), nullable=True),
        sa.Column("color", sa.String(9), nullable=True),
        sa.Column("bookable", sa.Boolean, nullable=False, server_default=sa.text("true")),
        *_tstamps(),
        _soft_delete(),
    )

    op.create_table(
        "auth_lockouts",
        _pk(),
        sa.Column("email", sa.String(255), nullable=False, index=True),
        sa.Column("attempts", sa.Integer, nullable=False, server_default="0"),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        *_tstamps(),
    )

    op.create_table(
        "patients",
        _pk(),
        sa.Column("org_id", pg.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("mrn", sa.String(40), nullable=False),
        sa.Column("first_name", sa.String(80), nullable=False),
        sa.Column("last_name", sa.String(80), nullable=False),
        sa.Column("middle_name", sa.String(80), nullable=True),
        sa.Column("dob", sa.Date, nullable=False),
        sa.Column("sex", sa.String(1), nullable=True),
        sa.Column("email", sa.String(255), nullable=True, index=True),
        sa.Column("phone", sa.String(30), nullable=True),
        sa.Column("address", pg.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("preferred_office_id", pg.UUID(as_uuid=True), sa.ForeignKey("offices.id", ondelete="SET NULL"), nullable=True),
        sa.Column("sms_opt_in_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("merged_into_patient_id", pg.UUID(as_uuid=True), sa.ForeignKey("patients.id", ondelete="SET NULL"), nullable=True),
        *_tstamps(),
        _soft_delete(),
        sa.UniqueConstraint("org_id", "mrn", name="uq_patients_org_mrn"),
    )
    op.create_index("ix_patients_org_lastname", "patients", ["org_id", "last_name"])
    op.create_index("ix_patients_org_dob", "patients", ["org_id", "dob"])

    op.create_table(
        "patient_accounts",
        _pk(),
        sa.Column("patient_id", pg.UUID(as_uuid=True), sa.ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, unique=True, index=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True, index=True),
        sa.Column("password_hash", sa.String(255), nullable=True),
        sa.Column("auth_mode", sa.String(10), nullable=False, server_default="magic"),
        sa.Column("mfa_enrolled", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("totp_secret", sa.String(64), nullable=True),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        *_tstamps(),
        _soft_delete(),
    )

    op.create_table(
        "intake_forms",
        _pk(),
        sa.Column("org_id", pg.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("schema", pg.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        *_tstamps(),
        _soft_delete(),
    )

    op.create_table(
        "reminder_rules",
        _pk(),
        sa.Column("org_id", pg.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("offsets_min", pg.ARRAY(sa.Integer), nullable=False, server_default=sa.text("ARRAY[]::integer[]")),
        sa.Column("channels", pg.ARRAY(sa.String(10)), nullable=False, server_default=sa.text("ARRAY[]::varchar[]")),
        sa.Column("active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        *_tstamps(),
        _soft_delete(),
    )

    op.create_table(
        "appointment_types",
        _pk(),
        sa.Column("org_id", pg.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("duration_min", sa.Integer, nullable=False),
        sa.Column("buffer_before_min", sa.Integer, nullable=False, server_default="0"),
        sa.Column("buffer_after_min", sa.Integer, nullable=False, server_default="0"),
        sa.Column("color", sa.String(9), nullable=True),
        sa.Column("requires_provider", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("requires_resource", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("intake_form_id", pg.UUID(as_uuid=True), sa.ForeignKey("intake_forms.id", ondelete="SET NULL"), nullable=True),
        sa.Column("reminder_rule_id", pg.UUID(as_uuid=True), sa.ForeignKey("reminder_rules.id", ondelete="SET NULL"), nullable=True),
        sa.Column("cancellation_window_hours", sa.Integer, nullable=False, server_default="24"),
        sa.Column("active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        *_tstamps(),
        _soft_delete(),
    )

    op.create_table(
        "resources",
        _pk(),
        sa.Column("org_id", pg.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("office_id", pg.UUID(as_uuid=True), sa.ForeignKey("offices.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("kind", sa.String(40), nullable=False, server_default="room"),
        *_tstamps(),
        _soft_delete(),
    )

    op.create_table(
        "recurring_appointment_series",
        _pk(),
        sa.Column("org_id", pg.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("rrule", sa.String(500), nullable=False),
        sa.Column("dtstart", sa.DateTime(timezone=True), nullable=False),
        sa.Column("until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("exdates", pg.JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("template", pg.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        *_tstamps(),
        _soft_delete(),
    )

    op.create_table(
        "appointments",
        _pk(),
        sa.Column("org_id", pg.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("office_id", pg.UUID(as_uuid=True), sa.ForeignKey("offices.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("provider_id", pg.UUID(as_uuid=True), sa.ForeignKey("provider_profiles.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("patient_id", pg.UUID(as_uuid=True), sa.ForeignKey("patients.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("appointment_type_id", pg.UUID(as_uuid=True), sa.ForeignKey("appointment_types.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("resource_id", pg.UUID(as_uuid=True), sa.ForeignKey("resources.id", ondelete="SET NULL"), nullable=True),
        sa.Column("series_id", pg.UUID(as_uuid=True), sa.ForeignKey("recurring_appointment_series.id", ondelete="SET NULL"), nullable=True),
        sa.Column("occurrence_date", sa.Date, nullable=True),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_min", sa.Integer, nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="scheduled"),
        sa.Column("source", sa.String(10), nullable=False, server_default="staff"),
        sa.Column("confirm_token_hash", sa.String(128), nullable=True),
        sa.Column("cancel_token_hash", sa.String(128), nullable=True),
        sa.Column("canceled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("canceled_by_actor_type", sa.String(20), nullable=True),
        sa.Column("cancel_reason", sa.String(500), nullable=True),
        sa.Column("no_show_marked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.String(2000), nullable=True),
        *_tstamps(),
        _soft_delete(),
    )
    op.create_index("ix_appt_org_provider_start", "appointments", ["org_id", "provider_id", "start_at"])
    op.create_index("ix_appt_org_patient_start", "appointments", ["org_id", "patient_id", "start_at"])
    op.create_index("ix_appt_org_status_start", "appointments", ["org_id", "status", "start_at"])

    # Conflict prevention: overlapping tstzrange per provider (active statuses only).
    op.execute("""
    ALTER TABLE appointments
    ADD CONSTRAINT excl_appt_provider_overlap
    EXCLUDE USING gist (
        provider_id WITH =,
        tstzrange(start_at, end_at, '[)') WITH &&
    )
    WHERE (
        deleted_at IS NULL
        AND status IN ('scheduled','confirmed','checked_in','completed')
    );
    """)
    op.execute("""
    ALTER TABLE appointments
    ADD CONSTRAINT excl_appt_resource_overlap
    EXCLUDE USING gist (
        resource_id WITH =,
        tstzrange(start_at, end_at, '[)') WITH &&
    )
    WHERE (
        resource_id IS NOT NULL
        AND deleted_at IS NULL
        AND status IN ('scheduled','confirmed','checked_in','completed')
    );
    """)

    op.create_table(
        "provider_availability",
        _pk(),
        sa.Column("org_id", pg.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("provider_id", pg.UUID(as_uuid=True), sa.ForeignKey("provider_profiles.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("office_id", pg.UUID(as_uuid=True), sa.ForeignKey("offices.id", ondelete="CASCADE"), nullable=True),
        sa.Column("weekday", sa.Integer, nullable=False),
        sa.Column("start_time", sa.Time, nullable=False),
        sa.Column("end_time", sa.Time, nullable=False),
        sa.Column("effective_from", sa.Date, nullable=True),
        sa.Column("effective_until", sa.Date, nullable=True),
        *_tstamps(),
        _soft_delete(),
    )

    op.create_table(
        "time_off",
        _pk(),
        sa.Column("org_id", pg.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("provider_id", pg.UUID(as_uuid=True), sa.ForeignKey("provider_profiles.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.String(200), nullable=True),
        *_tstamps(),
        _soft_delete(),
    )

    op.create_table(
        "waitlist_entries",
        _pk(),
        sa.Column("org_id", pg.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("patient_id", pg.UUID(as_uuid=True), sa.ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("appointment_type_id", pg.UUID(as_uuid=True), sa.ForeignKey("appointment_types.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("provider_pref_id", pg.UUID(as_uuid=True), sa.ForeignKey("provider_profiles.id", ondelete="SET NULL"), nullable=True),
        sa.Column("office_id", pg.UUID(as_uuid=True), sa.ForeignKey("offices.id", ondelete="SET NULL"), nullable=True),
        sa.Column("earliest_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("latest_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("notified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("booked_appointment_id", pg.UUID(as_uuid=True), sa.ForeignKey("appointments.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column("notes", sa.String(500), nullable=True),
        *_tstamps(),
        _soft_delete(),
    )

    op.create_table(
        "intake_submissions",
        _pk(),
        sa.Column("org_id", pg.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("form_id", pg.UUID(as_uuid=True), sa.ForeignKey("intake_forms.id", ondelete="RESTRICT"), nullable=False, index=True),
        sa.Column("form_version", sa.Integer, nullable=False),
        sa.Column("patient_id", pg.UUID(as_uuid=True), sa.ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("appointment_id", pg.UUID(as_uuid=True), sa.ForeignKey("appointments.id", ondelete="SET NULL"), nullable=True),
        sa.Column("answers", pg.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("signed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("signature_name", sa.String(120), nullable=True),
        *_tstamps(),
        _soft_delete(),
    )

    op.create_table(
        "consents",
        _pk(),
        sa.Column("org_id", pg.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("patient_id", pg.UUID(as_uuid=True), sa.ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("kind", sa.String(30), nullable=False),
        sa.Column("document_version", sa.String(30), nullable=False),
        sa.Column("body_hash", sa.String(128), nullable=False),
        sa.Column("signed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("signer_name", sa.String(120), nullable=False),
        sa.Column("signer_ip", sa.String(64), nullable=True),
        *_tstamps(),
        _soft_delete(),
    )

    op.create_table(
        "documents",
        _pk(),
        sa.Column("org_id", pg.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("patient_id", pg.UUID(as_uuid=True), sa.ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("mime_type", sa.String(100), nullable=False),
        sa.Column("size_bytes", sa.Integer, nullable=False),
        sa.Column("storage_key", sa.String(500), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("uploaded_by_actor_type", sa.String(20), nullable=False),
        sa.Column("uploaded_by_actor_id", pg.UUID(as_uuid=True), nullable=True),
        *_tstamps(),
        _soft_delete(),
    )

    op.create_table(
        "insurance_policies",
        _pk(),
        sa.Column("org_id", pg.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("patient_id", pg.UUID(as_uuid=True), sa.ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("priority", sa.Integer, nullable=False, server_default="1"),
        sa.Column("carrier", sa.String(120), nullable=False),
        sa.Column("plan_name", sa.String(120), nullable=True),
        sa.Column("member_id", sa.String(60), nullable=False),
        sa.Column("group_number", sa.String(60), nullable=True),
        sa.Column("subscriber_name", sa.String(160), nullable=True),
        sa.Column("subscriber_dob", sa.Date, nullable=True),
        sa.Column("subscriber_relation", sa.String(20), nullable=True),
        sa.Column("effective_date", sa.Date, nullable=True),
        sa.Column("termination_date", sa.Date, nullable=True),
        sa.Column("active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("card_document_id", pg.UUID(as_uuid=True), sa.ForeignKey("documents.id", ondelete="SET NULL"), nullable=True),
        sa.Column("extra", pg.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        *_tstamps(),
        _soft_delete(),
    )

    op.create_table(
        "api_keys",
        _pk(),
        sa.Column("org_id", pg.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("prefix", sa.String(12), nullable=False, index=True),
        sa.Column("key_hash", sa.String(128), nullable=False, unique=True, index=True),
        sa.Column("scopes", pg.ARRAY(sa.String(60)), nullable=False, server_default=sa.text("ARRAY[]::varchar[]")),
        sa.Column("created_by_user_id", pg.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        *_tstamps(),
        _soft_delete(),
    )

    op.create_table(
        "webhook_subscriptions",
        _pk(),
        sa.Column("org_id", pg.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("target_url", sa.String(500), nullable=False),
        sa.Column("events", pg.ARRAY(sa.String(60)), nullable=False, server_default=sa.text("ARRAY[]::varchar[]")),
        sa.Column("secret_hash", sa.String(128), nullable=False),
        sa.Column("active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_failure_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_count", sa.Integer, nullable=False, server_default="0"),
        *_tstamps(),
        _soft_delete(),
    )

    op.create_table(
        "webhook_deliveries",
        _pk(),
        sa.Column("org_id", pg.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("subscription_id", pg.UUID(as_uuid=True), sa.ForeignKey("webhook_subscriptions.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("event", sa.String(60), nullable=False),
        sa.Column("payload", pg.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("attempt", sa.Integer, nullable=False, server_default="1"),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("response_status", sa.Integer, nullable=True),
        sa.Column("response_body", sa.String(2000), nullable=True),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True, index=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        *_tstamps(),
    )

    op.create_table(
        "activity_log",
        _pk(),
        sa.Column("org_id", pg.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("actor_type", sa.String(20), nullable=False),
        sa.Column("actor_id", pg.UUID(as_uuid=True), nullable=True),
        sa.Column("actor_email", sa.String(255), nullable=True),
        sa.Column("entity_type", sa.String(60), nullable=False),
        sa.Column("entity_id", pg.UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.String(60), nullable=False),
        sa.Column("changes", pg.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("phi_accessed", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("ip", sa.String(64), nullable=True),
        sa.Column("user_agent", sa.String(500), nullable=True),
        sa.Column("request_id", sa.String(64), nullable=True),
        *_tstamps(),
    )
    op.create_index("ix_activity_org_created", "activity_log", ["org_id", "created_at"])
    op.create_index("ix_activity_org_entity", "activity_log", ["org_id", "entity_type", "entity_id"])
    op.create_index("ix_activity_org_actor", "activity_log", ["org_id", "actor_type", "actor_id"])
    op.create_index("ix_activity_org_phi", "activity_log", ["org_id", "phi_accessed", "created_at"])

    op.create_table(
        "notification_templates",
        _pk(),
        sa.Column("org_id", pg.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("channel", sa.String(10), nullable=False),
        sa.Column("event", sa.String(60), nullable=False),
        sa.Column("subject", sa.String(255), nullable=True),
        sa.Column("body", sa.String(8000), nullable=False),
        sa.Column("active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        *_tstamps(),
        _soft_delete(),
    )

    op.create_table(
        "notification_log",
        _pk(),
        sa.Column("org_id", pg.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("channel", sa.String(10), nullable=False),
        sa.Column("event", sa.String(60), nullable=False),
        sa.Column("appointment_id", pg.UUID(as_uuid=True), sa.ForeignKey("appointments.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("patient_id", pg.UUID(as_uuid=True), sa.ForeignKey("patients.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("to_address", sa.String(255), nullable=False),
        sa.Column("provider_message_id", sa.String(255), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="queued"),
        sa.Column("error", sa.String(500), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("context", pg.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        *_tstamps(),
    )

    op.create_table(
        "calendar_connections",
        _pk(),
        sa.Column("org_id", pg.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("user_id", pg.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("account_email", sa.String(255), nullable=False),
        sa.Column("calendar_id", sa.String(255), nullable=False),
        sa.Column("access_token_ct", sa.String(4000), nullable=False),
        sa.Column("refresh_token_ct", sa.String(4000), nullable=True),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sync_token", sa.String(2000), nullable=True),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("scopes", pg.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        *_tstamps(),
        _soft_delete(),
    )

    op.create_table(
        "magic_link_tokens",
        _pk(),
        sa.Column("org_id", pg.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("patient_account_id", pg.UUID(as_uuid=True), sa.ForeignKey("patient_accounts.id", ondelete="CASCADE"), nullable=True, index=True),
        sa.Column("email", sa.String(255), nullable=False, index=True),
        sa.Column("token_hash", sa.String(128), nullable=False, unique=True, index=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ip_issued", sa.String(64), nullable=True),
        *_tstamps(),
    )

    op.create_table(
        "confirm_tokens",
        _pk(),
        sa.Column("org_id", pg.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("appointment_id", pg.UUID(as_uuid=True), sa.ForeignKey("appointments.id", ondelete="CASCADE"), nullable=True, index=True),
        sa.Column("patient_id", pg.UUID(as_uuid=True), sa.ForeignKey("patients.id", ondelete="CASCADE"), nullable=True),
        sa.Column("token_hash", sa.String(128), nullable=False, unique=True, index=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        *_tstamps(),
    )

    op.create_table(
        "usage_events",
        _pk(),
        sa.Column("org_id", pg.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("kind", sa.String(60), nullable=False, index=True),
        sa.Column("quantity", sa.Integer, nullable=False, server_default="1"),
        sa.Column("actor_type", sa.String(20), nullable=True),
        sa.Column("actor_id", pg.UUID(as_uuid=True), nullable=True),
        sa.Column("context", pg.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        *_tstamps(),
    )


def downgrade() -> None:
    # No downgrade for the baseline; recreate the DB instead.
    raise NotImplementedError("Baseline migration cannot be downgraded.")
