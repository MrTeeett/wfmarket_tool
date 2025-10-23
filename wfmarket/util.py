import time
from contextlib import contextmanager

from .config import get_config_value


RATE_DELAY = float(get_config_value("limits", "rate_delay", default=0.35))


def sleep() -> None:
        time.sleep(RATE_DELAY)


@contextmanager
def rate_limited():
        try:
                yield
        finally:
                sleep()


def set_rate_delay(value: float) -> None:
        """Update the global rate limit delay in seconds."""
        global RATE_DELAY
        try:
                RATE_DELAY = max(0.0, float(value))
        except (TypeError, ValueError):
                return
