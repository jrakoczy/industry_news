from typing import List, Optional, Type, TypeVar, Tuple
import logging
import requests
import urllib
from bs4 import BeautifulSoup
from requests.models import Response
from industry_news.utils import delay_random, fail_gracefully

LOGGER = logging.getLogger(__name__)
RETRIES = 3
DELAY_RANGE: Tuple[int, int] = (1, 3)
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
    delay_range: Tuple[int, int] = DELAY_RANGE,
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


def fetch_site_texts(urls: List[urllib.parse.ParseResult]) -> List[str]:
    responses: List[Response] = [
        response
        for url in urls
        if (response := _send_request(url)) is not None
    ]
    texts: List[str] = [
        text
        for response in responses
        if (text := _retrieve_text(response)) is not None
    ]
    return texts


def _send_request(url: urllib.parse.ParseResult) -> Optional[Response]:
    LOGGER.info(f"Retrieving article from {url.geturl()}")
    response: Optional[Response] = fail_gracefully(
        lambda: get_with_retries(url)
    )
    return response


def _retrieve_text(response: Response) -> Optional[str]:
    soup: BeautifulSoup = BeautifulSoup(response.content, "html.parser")
    return fail_gracefully(soup.get_text)
