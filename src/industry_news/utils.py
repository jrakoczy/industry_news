import logging
from typing import Callable, Optional, TypeVar

T = TypeVar("T")


def fail_gracefully(func: Callable[..., T], *args, **kwargs) -> Optional[T]:
    try:
        return func(*args, **kwargs)
    except Exception as e:
        logging.exception(e)
        return None
