"""Async SQLAlchemy engine + session factory."""
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

engine = create_async_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    echo=False,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    pass


# Tamper-evident audit chaining: assign the ActivityLog hash chain at flush
# time. Registered on the sync Session class that the async session drives, so
# the handler runs inside the flush's live connection and can read the current
# chain head. Imported lazily inside the handler to avoid an import cycle
# (audit_chain imports the ActivityLog model).
from sqlalchemy import event  # noqa: E402
from sqlalchemy.orm import Session as _SyncSession  # noqa: E402


@event.listens_for(_SyncSession, "before_flush")
def _assign_audit_chain(session, _flush_context, _instances) -> None:
    from app.services.audit_chain import assign_chain

    assign_chain(session)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
