"""Import every model so Alembic's autogenerate sees them on Base.metadata."""
from app.models.base import Base  # noqa: F401

from app.models.organization import Organization  # noqa: F401
from app.models.office import Office  # noqa: F401
from app.models.user import User, ProviderProfile, AuthLockout  # noqa: F401
from app.models.patient import Patient, PatientAccount  # noqa: F401
from app.models.appointment_type import AppointmentType, Resource  # noqa: F401
from app.models.appointment import Appointment, RecurringAppointmentSeries  # noqa: F401
from app.models.availability import ProviderAvailability, TimeOff  # noqa: F401
from app.models.waitlist import WaitlistEntry  # noqa: F401
from app.models.intake_form import IntakeForm, IntakeSubmission  # noqa: F401
from app.models.patient_records import Consent, Document, InsurancePolicy  # noqa: F401
from app.models.api_key import ApiKey  # noqa: F401
from app.models.webhook import WebhookSubscription, WebhookDelivery  # noqa: F401
from app.models.activity_log import ActivityLog  # noqa: F401
from app.models.notification import (  # noqa: F401
    NotificationTemplate,
    NotificationLog,
    ReminderRule,
)
from app.models.calendar_connection import CalendarConnection  # noqa: F401
from app.models.calendar_sync_link import CalendarSyncLink  # noqa: F401
from app.models.tokens import MagicLinkToken, ConfirmToken  # noqa: F401
from app.models.usage import UsageEvent  # noqa: F401
