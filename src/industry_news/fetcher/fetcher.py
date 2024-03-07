from datetime import datetime
from abc import ABC, abstractmethod
from enum import Enum
from urllib.parse import ParseResult
import logging
from typing import List, Optional
from bs4 import BeautifulSoup
from industry_news.fetcher.article import ArticleMetadata
from industry_news.fetcher.web_tools import get_with_retries
from requests.models import Response
from industry_news.utils import fail_gracefully

LOGGER = logging.getLogger(__name__)


class CONTINUE_PAGINATING(Enum):
    CONTINUE = True
    STOP = False


class Fetcher(ABC):
    @abstractmethod
    def articles_metadata(
        self, since: datetime, until: datetime
    ) -> List[ArticleMetadata]:
        pass


def fetch_sites_texts(urls: List[ParseResult]) -> List[str]:
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


def _send_request(url: ParseResult) -> Optional[Response]:
    LOGGER.info(f"Retrieving article from {url.geturl()}")
    response: Optional[Response] = fail_gracefully(
        lambda: get_with_retries(url)
    )
    return response


def _retrieve_text(response: Response) -> Optional[str]:
    soup: BeautifulSoup = BeautifulSoup(response.content, "html.parser")
    return fail_gracefully(soup.get_text)
