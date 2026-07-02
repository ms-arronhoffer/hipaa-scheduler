import logging
import os

import uvicorn

from app.config import settings

logger = logging.getLogger(__name__)


def run_migrations() -> None:
    """Upgrade the database to the latest Alembic revision before serving.

    Idempotent: a database already at ``head`` is a no-op. Runs in this
    synchronous context (no event loop yet) so the async migration env can spin
    up its own loop.
    """
    from alembic import command
    from alembic.config import Config

    here = os.path.dirname(os.path.abspath(__file__))
    cfg = Config(os.path.join(here, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(here, "alembic"))
    logger.info("startup.migrations_begin")
    command.upgrade(cfg, "head")
    logger.info("startup.migrations_done")


if __name__ == "__main__":
    if settings.run_migrations_on_startup:
        run_migrations()
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        workers=1,
        log_config=None,
        proxy_headers=True,
        forwarded_allow_ips="*",
        reload=settings.app_env == "development",
    )
