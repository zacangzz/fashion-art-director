import io
import sys
import logging
from app.utils.logger import get_logger, setup_logging, set_request_context

def test_logger_stdout_output():
    # Test formatting with a custom stream handler
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    
    root_logger = get_logger("test_module")
    # Verify handler formatting
    root_handler = root_logger.handlers[0] if root_logger.handlers else root_logger.parent.handlers[0]
    
    # Test logging record formatting
    record = root_logger.makeRecord(
        name="studio.test_module",
        level=logging.INFO,
        fn="test_logger.py",
        lno=15,
        msg="Hello Cloud Logging",
        args=(),
        exc_info=None,
    )
    for f in root_handler.filters:
        f.filter(record)
    formatted = root_handler.format(record)
    assert "Hello Cloud Logging" in formatted
    assert "[studio.test_module]" in formatted
    assert "[req:none]" in formatted

def test_logger_request_id_injection():
    root_logger = get_logger("test_req_module")
    root_handler = root_logger.handlers[0] if root_logger.handlers else root_logger.parent.handlers[0]
    
    set_request_context(request_id="req_abc123_xyz")
    record = root_logger.makeRecord(
        name="studio.test_req_module",
        level=logging.INFO,
        fn="test_logger.py",
        lno=30,
        msg="Processing request",
        args=(),
        exc_info=None,
    )
    for f in root_handler.filters:
        f.filter(record)
    formatted = root_handler.format(record)
    assert "[req:req_abc123_xyz]" in formatted
    assert "Processing request" in formatted
    set_request_context(request_id=None)

def test_no_log_files_created():
    root_logger = logging.getLogger("studio")
    for handler in root_logger.handlers:
        assert not isinstance(handler, logging.FileHandler)
