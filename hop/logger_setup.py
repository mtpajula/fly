# first_hop/logger_setup.py

import logging
from . import config


def setup_logger() -> logging.Logger:
    logger = logging.getLogger("first_hop")

    if logger.handlers:
        return logger  # already configured

    level = getattr(logging, config.LOG_LEVEL.upper(), logging.INFO)
    logger.setLevel(level)

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    logger.addHandler(console)

    if config.LOG_TO_FILE:
        file_handler = logging.FileHandler(config.LOG_FILE_PATH)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger
