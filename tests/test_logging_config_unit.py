"""Unit tests for scripts/logging_config.py."""
from __future__ import annotations

import logging
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


@pytest.fixture
def logcfg():
    sys.path.insert(0, str(SCRIPTS_DIR))
    import logging_config
    yield logging_config
    if str(SCRIPTS_DIR) in sys.path:
        sys.path.remove(str(SCRIPTS_DIR))


class TestSetupLogging:
    def test_creates_log_dir(self, logcfg, tmp_path):
        """Logs directory is created if it doesn't exist."""
        log_dir = tmp_path / "logs"
        logcfg.setup_logging(log_dir=str(log_dir))
        assert log_dir.exists()
        assert log_dir.is_dir()

    def test_creates_log_file(self, logcfg, tmp_path):
        """workflow.log is created in log_dir."""
        log_dir = tmp_path / "logs"
        logcfg.setup_logging(log_dir=str(log_dir))
        log_file = log_dir / "workflow.log"
        assert log_file.exists()

    def test_returns_logger(self, logcfg, tmp_path):
        """Returns a Logger instance."""
        log_dir = tmp_path / "logs"
        logger = logcfg.setup_logging(log_dir=str(log_dir))
        assert isinstance(logger, logging.Logger)

    def test_logger_name(self, logcfg, tmp_path):
        logger = logcfg.setup_logging(log_dir=str(tmp_path / "logs"))
        assert logger.name == "finai"

    def test_default_level_info(self, logcfg, tmp_path):
        logger = logcfg.setup_logging(log_dir=str(tmp_path / "logs"))
        assert logger.level == logging.INFO

    def test_custom_level(self, logcfg, tmp_path):
        logger = logcfg.setup_logging(log_dir=str(tmp_path / "logs"), level=logging.DEBUG)
        assert logger.level == logging.DEBUG

    def test_no_console_when_disabled(self, logcfg, tmp_path):
        logger = logcfg.setup_logging(log_dir=str(tmp_path / "logs"), console=False)
        # All handlers should be file-based (RotatingFileHandler)
        stream_handlers = [h for h in logger.handlers if isinstance(h, logging.StreamHandler)
                          and not isinstance(h, logging.handlers.RotatingFileHandler)]
        assert stream_handlers == []

    def test_console_when_enabled(self, logcfg, tmp_path):
        logger = logcfg.setup_logging(log_dir=str(tmp_path / "logs"), console=True)
        # At least one StreamHandler other than file handler
        stream_handlers = [h for h in logger.handlers if type(h) is logging.StreamHandler]
        assert len(stream_handlers) >= 1

    def test_clears_previous_handlers(self, logcfg, tmp_path):
        """Calling setup twice doesn't double handlers."""
        log_dir = tmp_path / "logs"
        logcfg.setup_logging(log_dir=str(log_dir))
        first_handler_count = len(logcfg.setup_logging(log_dir=str(log_dir)).handlers)
        logcfg.setup_logging(log_dir=str(log_dir))
        logger = logging.getLogger("finai")
        assert len(logger.handlers) == first_handler_count

    def test_writes_to_log_file(self, logcfg, tmp_path):
        logger = logcfg.setup_logging(log_dir=str(tmp_path / "logs"))
        logger.info("hello world")
        # Flush handlers
        for h in logger.handlers:
            h.flush()
        content = (tmp_path / "logs" / "workflow.log").read_text()
        assert "hello world" in content


class TestGetLogger:
    def test_get_logger_returns_child(self, logcfg):
        """get_logger returns a child of finai."""
        child = logcfg.get_logger("data_pipeline")
        assert child.name == "finai.data_pipeline"

    def test_get_logger_returns_logger_instance(self, logcfg):
        child = logcfg.get_logger("llm")
        assert isinstance(child, logging.Logger)

    def test_get_logger_with_subpath(self, logcfg):
        child = logcfg.get_logger("a.b.c")
        assert child.name == "finai.a.b.c"

    def test_get_logger_called_multiple_times_returns_same(self, logcfg):
        """Logging.getLogger returns the same instance for the same name."""
        l1 = logcfg.get_logger("module1")
        l2 = logcfg.get_logger("module1")
        assert l1 is l2

