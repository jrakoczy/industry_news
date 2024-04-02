from datetime import datetime
from abc import ABC, abstractmethod
from enum import Enum
from urllib.parse import ParseResult
import logging
from typing import Callable, Dict, List, Optional
from bs4 import BeautifulSoup
from industry_news.config import SingleSourceConfig, SourcesConfig
from industry_news.digest.article import ArticleSummary, ArticleMetadata
from industry_news.fetcher.futuretools_scraper import FutureToolsScraper
from industry_news.fetcher.hackernews_scraper import HackerNewsScraper
from industry_news.fetcher.reddit_api import RedditApi
from industry_news.fetcher.researchhub_api import ResearchHubApi
from industry_news.fetcher.web_tools import get_with_retries
from requests.models import Response
from industry_news.utils import fail_gracefully

LOGGER = logging.getLogger(__name__)


class Source(Enum):
    REDDIT = "reddit"
    HACKER_NEWS = "hackernews"
    RESEARCH_HUB = "researchhub"
    FUTURE_TOOLS = "futuretools"


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


SUMMARY_FETCHERS_BY_SOURCE: Dict[Source, Callable[[], SummaryFetcher]] = {
    Source.RESEARCH_HUB: lambda: ResearchHubApi()
}

METADATA_FETCHERS_BY_SOURCE: Dict[
    Source, Callable[[Optional[str]], MetadataFetcher]
] = {
    Source.REDDIT: lambda subspace: _reddit_api(subspace),
    Source.HACKER_NEWS: lambda _: HackerNewsScraper(),
    Source.FUTURE_TOOLS: lambda _: FutureToolsScraper(),
}


def init_summary_fetchers(
    sources_config: SourcesConfig,
) -> List[SummaryFetcher]:
    with_summary_sources: List[SingleSourceConfig] = (
        sources_config.with_summary
    )
    return [
        SUMMARY_FETCHERS_BY_SOURCE[config.name]()
        for config in with_summary_sources
    ]


def init_metadata_fetchers(
    sources_config: SourcesConfig,
) -> List[MetadataFetcher]:
    without_summary_sources: List[SingleSourceConfig] = (
        sources_config.without_summary
    )
    fetchers: List[MetadataFetcher] = []

    for config in without_summary_sources:
        if config.subspaces:
            for subspace in config.subspaces:
                fetchers.append(
                    METADATA_FETCHERS_BY_SOURCE[config.name](subspace)
                )
        else:
            fetchers.append(METADATA_FETCHERS_BY_SOURCE[config.name](""))

    return fetchers


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


def _reddit_api(subreddit: Optional[str]) -> RedditApi:
    if subreddit:
        return RedditApi(subreddit)
    else:
        raise ValueError("Subreddit name not provided.")
