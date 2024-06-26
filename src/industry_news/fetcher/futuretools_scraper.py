from datetime import datetime, timezone
import logging
from bs4 import BeautifulSoup
from typing import List, Optional
from requests.models import Response
from urllib.parse import urlparse, ParseResult
from industry_news.digest.article import ArticleMetadata
from industry_news.sources import Source
from industry_news.fetcher.fetcher import (
    MetadataFetcher,
)
from industry_news.fetcher.web_tools import verify_page_element
from .web_tools import construct_url, get_with_retries
from bs4.element import Tag


class FutureToolsScraper(MetadataFetcher):

    _LOGGER = logging.getLogger(__name__)
    _BASE_URL: str = "https://www.futuretools.io"
    _SITE_LINK: ParseResult = construct_url(_BASE_URL, "news")

    def __init__(self, site_link: ParseResult = _SITE_LINK) -> None:
        self._site_link = site_link

    @staticmethod
    def source() -> Source:
        return Source.FUTURE_TOOLS

    def subspace(self) -> Optional[str]:
        return None

    def articles_metadata(
        self, since: datetime, until: datetime
    ) -> List[ArticleMetadata]:
        self._LOGGER.info(
            "Fetching articles from FutureTools between %s and %s",
            since,
            until,
        )
        response: Response = get_with_retries(url=self._site_link)
        soup: BeautifulSoup = BeautifulSoup(response.content, "html.parser")
        return FutureToolsScraper._articles_from_page(
            soup=soup, since=since, until=until
        )

    @staticmethod
    def _articles_from_page(
        soup: BeautifulSoup, since: datetime, until: datetime
    ) -> List[ArticleMetadata]:
        articles: List[ArticleMetadata] = []
        list_div: Tag = verify_page_element(soup.find("div", role="list"), Tag)
        list_items: List[Tag] = list_div.find_all("div", role="listitem")

        for item in list_items:
            publication_date: datetime = (
                FutureToolsScraper._single_article_publication_date(item)
            )

            if publication_date > until:
                continue
            elif publication_date < since:
                break

            articles.append(
                ArticleMetadata(
                    title=FutureToolsScraper._single_article_title(item),
                    source=Source.FUTURE_TOOLS,
                    url=FutureToolsScraper._single_article_url(item),
                    publication_date_utc=publication_date,
                    score=0,  # No scores on the site
                )
            )

        return articles

    @staticmethod
    def _single_article_url(div: Tag) -> ParseResult:
        link_tag: Tag = verify_page_element(div.find("a"), Tag)
        url: str = verify_page_element(link_tag["href"], str)
        return urlparse(url)

    @staticmethod
    def _single_article_title(div: Tag) -> str:
        link_tag: Tag = verify_page_element(div.find("a"), Tag)
        first_div: Tag = verify_page_element(link_tag.find("div"), Tag)
        return first_div.get_text()

    @staticmethod
    def _single_article_publication_date(div: Tag) -> datetime:
        """We assume the date is in UTC."""
        date_div: Tag = verify_page_element(
            div.findChildren("div", recursive=False)[0], Tag
        )
        date_text: str = date_div.get_text()
        return datetime.strptime(date_text, "%B %d, %Y").replace(
            tzinfo=timezone.utc
        )
