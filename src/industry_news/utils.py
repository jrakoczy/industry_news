import logging
import random
import time
import yaml
from typing import Callable, Optional, Tuple, TypeVar
from typing import Dict, Any

T = TypeVar("T")


def load_secrets() -> Dict[str, Any]:
    with open("secrets.yml", "r") as file:
        config: Dict[str, Any] = yaml.safe_load(file)
    return config


def delay_random(delay_range_s: Tuple[int, int]):
    delay: float = random.uniform(delay_range_s[0], delay_range_s[1])
    time.sleep(delay)


def fail_gracefully(func: Callable[..., T], *args, **kwargs) -> Optional[T]:
    try:
        return func(*args, **kwargs)
    except Exception as e:
        logging.exception(e)
        return None