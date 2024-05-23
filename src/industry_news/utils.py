from datetime import datetime, timezone
from importlib.abc import Traversable
import importlib.resources
import logging
import os
from pathlib import Path
import random
import time
import yaml
from typing import Callable, Optional, Tuple, TypeVar
from typing import Dict, Any

T = TypeVar("T")
RETRIES = 3


def to_utc_datetime(timestamp: int) -> datetime:
    return datetime.fromtimestamp(timestamp, tz=timezone.utc)


def load_resource(resource: str) -> Path:
    path: Traversable = importlib.resources.files("resources").joinpath(
        resource
    )
    if isinstance(path, os.PathLike):
        return Path(path)
    else:
        raise ValueError(f"Resource {resource} not found or not a file.")


def load_as_string(resource: str) -> str:
    with load_resource(resource).open("r") as file:
        return file.read()


def load_as_yml(resource: str) -> Dict[str, Any]:
    with load_resource(resource).open("r") as file:
        config: Dict[str, Any] = yaml.safe_load(file)
    return config


def delay_random(delay_range_s: Tuple[float, float]) -> None:
    delay: float = random.uniform(delay_range_s[0], delay_range_s[1])
    time.sleep(delay)


def fail_gracefully(func: Callable[..., T]) -> Optional[T]:
    try:
        return func()
    except Exception as e:
        logging.exception(e)
        return None


def retry(
    func: Callable[..., T],
    delay_range_s: Tuple[float, float],
    retries: int = RETRIES,
) -> T:
    for _ in range(retries - 1):
        try:
            return func()
        except Exception as e:
            logging.exception(e)
            delay_random(delay_range_s)
    return func()


def load_datetime_from_file(file_path: Path) -> Optional[datetime]:
    if file_path.exists():
        with open(file_path, "r") as file:
            date_string = file.readline().strip()
            return datetime.fromisoformat(date_string)
    else:
        return None


def write_datetime_to_file(file_path: Path, date_time: datetime) -> None:
    with open(file_path, "w") as file:
        file.write(date_time.isoformat())
