# ============================================================
#  utils/logger.py
#  Centralised logging setup
# ============================================================

import logging
import os
from datetime import datetime

LOG_DIR  = "logs"
LOG_FILE = os.path.join(LOG_DIR, f"traffic_{datetime.now():%Y%m%d}.log")


def setup_logger(name: str, level: int = logging.DEBUG) -> logging.Logger:
    """
    Return a named logger that writes to both console and a daily log file.
    """
    os.makedirs(LOG_DIR, exist_ok=True)

    logger = logging.getLogger(name)
    if logger.handlers:
        return logger   # already configured

    logger.setLevel(level)
    fmt = logging.Formatter(
        "%(asctime)s  [%(levelname)-8s]  %(name)s — %(message)s",
        datefmt="%H:%M:%S",
    )

    # Console handler
    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    ch.setLevel(logging.INFO)
    logger.addHandler(ch)

    # File handler
    fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
    fh.setFormatter(fmt)
    fh.setLevel(logging.DEBUG)
    logger.addHandler(fh)

    return logger
