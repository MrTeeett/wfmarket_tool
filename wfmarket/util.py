import time
from contextlib import contextmanager
from .config import get_config_value

RATE_DELAY = float(get_config_value("limits", "rate_delay", default=0.35))

def sleep():
	time.sleep(RATE_DELAY)

@contextmanager
def rate_limited():
	try:
		yield
	finally:
		sleep()
