import logging

LOG_FORMAT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"


def configure_logging(level: str) -> None:
    """Configure process-wide logging once at application startup."""
    logging.basicConfig(level=level.upper(), format=LOG_FORMAT, force=True)
