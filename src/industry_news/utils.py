import logging
import random
import time
from typing import Callable, Optional, Tuple, TypeVar

T = TypeVar("T")


def delay_random(delay_range_s: Tuple[int, int]):
    delay: float = random.uniform(delay_range_s[0], delay_range_s[1])
    time.sleep(delay)


def fail_gracefully(func: Callable[..., T], *args, **kwargs) -> Optional[T]:
    try:
        return func(*args, **kwargs)
    except Exception as e:
        logging.exception(e)
        return None
