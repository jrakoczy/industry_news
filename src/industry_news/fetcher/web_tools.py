from typing import Optional, Type, TypeVar, Tuple
import requests
import urllib
from industry_news.utils import delay_random

RETRIES = 3
DELAY_RANGE_S: Tuple[int, int] = (1, 3)
USER_AGENT: str = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    + "(KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"
)

T = TypeVar("T")
R = TypeVar("R")


def verify_page_element(element: Optional[T], type_: Type[R]) -> R:
    if not isinstance(element, type_):
        raise ValueError("Invalid page element.")
    return element


def get_with_retries(
    url: urllib.parse.ParseResult,
    retries: int = RETRIES,
    delay_range: Tuple[int, int] = DELAY_RANGE_S,
    user_agent: str = USER_AGENT,
) -> requests.models.Response:
    for _ in range(retries - 1):
        try:
            headers: dict = {"User-Agent": user_agent}
            response: requests.models.Response = requests.get(
                url=url.geturl(), headers=headers
            )
            return response
        except requests.RequestException:
            delay_random(delay_range)
    return requests.get(url=url.geturl(), headers=headers)
