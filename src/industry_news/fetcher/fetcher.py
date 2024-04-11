from datetime import datetime
from abc import ABC, abstractmethod
from enum import Enum
from urllib.parse import ParseResult
import logging
from typing import List, Optional
from bs4 import BeautifulSoup
from industry_news.digest.article import ArticleSummary, ArticleMetadata
from industry_news.sources import Source
from industry_news.fetcher.web_tools import get_with_retries
from requests.models import Response
from industry_news.utils import fail_gracefully

LOGGER = logging.getLogger(__name__)


class CONTINUE_PAGINATING(Enum):
    CONTINUE = True
    STOP = False


class Fetcher(ABC):
    @staticmethod
    @abstractmethod
    def source() -> Source:
        pass

    @abstractmethod
    def subspace(self) -> Optional[str]:
        """
        E.g. a subreddit or a tag. In general: a subcategory of data from a
        given source.
        """
        pass


class MetadataFetcher(Fetcher):
    @abstractmethod
    def articles_metadata(
        self, since: datetime, until: datetime
    ) -> List[ArticleMetadata]:
        pass


class SummaryFetcher(Fetcher):
    @abstractmethod
    def article_summaries(
        self, since: datetime, until: datetime
    ) -> List[ArticleSummary]:
        pass


def fetch_site_text(url: ParseResult) -> Optional[str]:
    text: Optional[str] = None
    response: Optional[Response] = _send_request(url)

    if response is not None:
        text = _retrieve_text(response)

    return text


def _send_request(url: ParseResult) -> Optional[Response]:
    LOGGER.info(f"Retrieving article from {url.geturl()}")
    response: Optional[Response] = fail_gracefully(
        lambda: get_with_retries(url)
    )
    return response


def _retrieve_text(response: Response) -> Optional[str]:
    soup: BeautifulSoup = BeautifulSoup(response.content, "html.parser")
    return fail_gracefully(soup.get_text)
