import logging

from app.core.config import settings


LOG_FORMAT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"


def configure_logging() -> None:
    """
    Configure minimal application logging for local backend runs.
    """
    level = getattr(
        logging,
        settings.log_level.strip().upper(),
        logging.INFO,
    )

    logging.basicConfig(
        level=level,
        format=LOG_FORMAT,
    )
    logging.getLogger("app").setLevel(level)
