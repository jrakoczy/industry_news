from typing import Dict, Optional, Type, TypeVar, Tuple
import requests
from urllib.parse import urljoin, urlparse, urlunparse, urlencode, ParseResult
from industry_news.utils import delay_random

RETRIES: int = 3
DELAY_RANGE_S: Tuple[int, int] = (1, 3)
USER_AGENT: str = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    + "(KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"
)

T = TypeVar("T")
R = TypeVar("R")


def construct_url(
    base_url: str, relative_path: str, params: Dict[str, str]
) -> ParseResult:
    url: ParseResult = urlparse(base_url)
    new_path: str = urljoin(base_url, relative_path)
    new_query: str = urlencode(params)
    return ParseResult(
        scheme=url.scheme,
        netloc=url.netloc,
        path=new_path,
        params=url.params,
        query=new_query,
        fragment=url.fragment,
    )


def verify_page_element(element: Optional[T], type_: Type[R]) -> R:
    if not isinstance(element, type_):
        raise ValueError("Invalid page element.")
    return element


def get_with_retries(
    url: ParseResult,
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
