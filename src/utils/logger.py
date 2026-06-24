import logging
import sys
import os


def setup_logger(name: str = "uk-job-bot", level: str = None) -> logging.Logger:
    if level is None:
        from src.settings import settings
        level = settings.get("logging", {}).get("level", "INFO")

    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level))

    fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")

    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    logger.addHandler(sh)

    log_file = None
    try:
        from src.settings import settings
        log_file = settings.get("logging", {}).get("file")
    except Exception:
        pass

    if log_file:
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        fh = logging.FileHandler(log_file)
        fh.setFormatter(fmt)
        logger.addHandler(fh)

    return logger


logger = setup_logger()
