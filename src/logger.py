import logging
import os
import sys
from .config import LOG_LEVEL, LOG_FORMAT, LOG_DIR

def setup_logger(name: str):
    """
    Configures and returns a logger instance with console and file output.
    """
    # Create logs directory if not exists
    if not os.path.exists(LOG_DIR):
        os.makedirs(LOG_DIR)

    logger = logging.getLogger(name)
    logger.setLevel(LOG_LEVEL)

    # Avoid adding handlers multiple times if logger already exists
    if not logger.handlers:
        # Console Handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(LOG_LEVEL)
        console_formatter = logging.Formatter(LOG_FORMAT)
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)

        # File Handler
        file_path = os.path.join(LOG_DIR, f"{name}.log")
        file_handler = logging.FileHandler(file_path, encoding='utf-8')
        file_handler.setLevel(LOG_LEVEL)
        file_formatter = logging.Formatter(LOG_FORMAT)
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

    return logger
