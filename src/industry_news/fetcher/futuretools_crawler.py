from datetime import datetime
from bs4 import BeautifulSoup
from typing import List
from requests.models import Response
from urllib.parse import urljoin, urlparse, ParseResult
from industry_news.fetcher.fetcher import (
    ArticleMetadata,
    Fetcher,
)
from industry_news.fetcher.web_tools import verify_page_element
from .web_tools import get_with_retries
from bs4.element import Tag

BASE_URL: str = "https://www.futuretools.io"
SITE_LINK: ParseResult = urlparse(urljoin(BASE_URL, "news"))


class FutureToolsCrawler(Fetcher):

    def articles_metadata(
        self, since: datetime, until: datetime = datetime.now()
    ) -> List[ArticleMetadata]:
        response: Response = get_with_retries(url=SITE_LINK)
        soup: BeautifulSoup = BeautifulSoup(response.content, "html.parser")
        return FutureToolsCrawler._articles_from_page(
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
                FutureToolsCrawler._single_article_publication_date(item)
            )

            if publication_date > until:
                continue
            elif publication_date < since:
                break

            articles.append(
                ArticleMetadata(
                    url=FutureToolsCrawler._single_article_url(item),
                    publication_date=publication_date,
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
    def _single_article_publication_date(div: Tag) -> datetime:
        date_div: Tag = verify_page_element(
            div.findChildren("div", recursive=False)[0], Tag
        )
        date_text: str = date_div.get_text()
        return datetime.strptime(date_text, "%B %d, %Y")
