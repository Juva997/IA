import logging
import os
from logging.handlers import RotatingFileHandler


def configure_logging(level=logging.INFO, log_dir=None):
    # Formato simples e legível para execução local e CI
    if log_dir is None:
        log_dir = os.environ.get("LOG_DIR", os.path.join(os.getcwd(), "logs"))

    try:
        os.makedirs(log_dir, exist_ok=True)
    except Exception:
        pass

    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
    )

    root = logging.getLogger()
    root.setLevel(level)

    # Console handler (only add if not present)
    if not any(isinstance(h, logging.StreamHandler) for h in root.handlers):
        ch = logging.StreamHandler()
        ch.setFormatter(formatter)
        root.addHandler(ch)

    # Rotating file handlers for info and errors
    info_path = os.path.join(log_dir, "app.log")
    err_path = os.path.join(log_dir, "app.err.log")

    existing_files = set()
    for h in root.handlers:
        try:
            existing_files.add(getattr(h, "baseFilename", None))
        except Exception:
            continue

    if info_path not in existing_files:
        fh_info = RotatingFileHandler(info_path, maxBytes=5 * 1024 * 1024, backupCount=3)
        fh_info.setLevel(logging.INFO)
        fh_info.setFormatter(formatter)
        root.addHandler(fh_info)

    if err_path not in existing_files:
        fh_err = RotatingFileHandler(err_path, maxBytes=5 * 1024 * 1024, backupCount=3)
        fh_err.setLevel(logging.ERROR)
        fh_err.setFormatter(formatter)
        root.addHandler(fh_err)


def get_logger(name=None):
    return logging.getLogger(name)
