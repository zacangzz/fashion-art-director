import sys
import logging
from contextvars import ContextVar
from typing import Optional

# Context variable for correlating execution flow with HTTP request IDs
request_id_var: ContextVar[Optional[str]] = ContextVar("request_id", default=None)
trace_id_var: ContextVar[Optional[str]] = ContextVar("trace_id", default=None)


def get_current_request_id() -> Optional[str]:
    """Returns the current request ID from the execution context, if set."""
    return request_id_var.get()


def set_current_request_id(req_id: Optional[str]) -> None:
    """Sets the current request ID in the execution context."""
    request_id_var.set(req_id)


def get_current_trace_id() -> Optional[str]:
    """Returns the current trace ID from the execution context, if set."""
    return trace_id_var.get()


def set_current_trace_id(tr_id: Optional[str]) -> None:
    """Sets the current trace ID in the execution context."""
    trace_id_var.set(tr_id)


def set_request_context(request_id: Optional[str] = None, trace_id: Optional[str] = None) -> None:
    """Helper to set both request_id and trace_id in context."""
    set_current_request_id(request_id)
    if trace_id is not None:
        set_current_trace_id(trace_id)


class RequestContextFilter(logging.Filter):
    """
    Injects context-local request_id into standard log records.
    """
    def filter(self, record: logging.LogRecord) -> bool:
        req_id = get_current_request_id()
        record.request_id = req_id if req_id else "none"
        return True


def setup_logging(log_level: int = logging.INFO) -> logging.Logger:
    """
    Configures unified console logging for the Studio application.
    Outputs structured logs exclusively to stdout for Google Cloud Logging ingestion.
    """
    root_logger = logging.getLogger("studio")
    root_logger.setLevel(log_level)

    # Avoid duplicate handlers if already initialized
    if root_logger.handlers:
        return root_logger

    context_filter = RequestContextFilter()

    log_format = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] [%(name)s] [req:%(request_id)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(log_format)
    console_handler.addFilter(context_filter)
    root_logger.addHandler(console_handler)

    # Set third-party logger levels to reduce noise
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("google").setLevel(logging.WARNING)

    root_logger.info("Structured console logging initialized.")
    return root_logger


def get_logger(name: str) -> logging.Logger:
    """
    Returns a child logger under the 'studio' namespace.
    """
    setup_logging()
    return logging.getLogger(f"studio.{name}")
