import sys
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_DIR = Path(__file__).resolve().parents[3] / "storage" / "logs"
LOG_FILE = LOG_DIR / "studio.log"

def setup_logging(log_level: int = logging.INFO) -> logging.Logger:
    """
    Configures unified logging for the Studio application.
    Outputs to both Console (stdout) and a Rotating Log File (storage/logs/studio.log).
    """
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    root_logger = logging.getLogger("studio")
    root_logger.setLevel(log_level)

    # Avoid duplicate handlers if already initialized
    if root_logger.handlers:
        return root_logger

    log_format = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] [%(name)s:%(lineno)d] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # 1. Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(log_format)
    root_logger.addHandler(console_handler)

    # 2. Rotating File Handler (Max 10MB per file, up to 5 backups)
    try:
        file_handler = RotatingFileHandler(
            LOG_FILE,
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setLevel(log_level)
        file_handler.setFormatter(log_format)
        root_logger.addHandler(file_handler)
    except Exception as e:
        print(f"Warning: Could not initialize file logging at {LOG_FILE}: {e}")

    # Set third-party logger levels to reduce noise
    logging.getLogger("aiosqlite").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)

    root_logger.info(f"Logging initialized. Log file: {LOG_FILE}")
    return root_logger

def get_logger(name: str) -> logging.Logger:
    """
    Returns a child logger under the 'studio' namespace.
    """
    return logging.getLogger(f"studio.{name}")
