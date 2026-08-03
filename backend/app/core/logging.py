import logging
import sys


def setup_logging():
    """Configures structured logging for HARIKA backend."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    logger = logging.getLogger("harika")
    logger.info("Structured logging initialized.")
    return logger


logger = setup_logging()
