import logging

from app.core.logging import configure_logging


def test_configure_logging_applies_level_case_insensitively() -> None:
    configure_logging("debug")

    assert logging.getLogger().level == logging.DEBUG

    configure_logging("WARNING")

    assert logging.getLogger().level == logging.WARNING
