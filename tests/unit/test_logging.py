import structlog
from structlog.testing import capture_logs

from coverage.logging_config import configure_logging


class TestConfigureLogging:
    def test_configure_console_does_not_raise(self) -> None:
        configure_logging("console")

    def test_configure_json_does_not_raise(self) -> None:
        configure_logging("json")

    def test_log_event_is_captured_after_configure(self) -> None:
        configure_logging("console")
        with capture_logs() as cap:
            log = structlog.get_logger()
            log.info("test_event", key="value")
        assert len(cap) == 1
        assert cap[0]["event"] == "test_event"
        assert cap[0]["key"] == "value"

    def test_log_level_is_present_in_captured_event(self) -> None:
        configure_logging("console")
        with capture_logs() as cap:
            structlog.get_logger().info("evt")
        assert cap[0]["log_level"] == "info"
