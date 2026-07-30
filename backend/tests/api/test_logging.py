import logging

import pytest
from pytest import MonkeyPatch

from app.core import logging_config


pytestmark = pytest.mark.no_db


def test_configure_logging_sets_application_logger_level(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        logging_config.settings,
        "log_level",
        "DEBUG",
    )

    logging_config.configure_logging()

    assert logging.getLogger("app").level == logging.DEBUG
