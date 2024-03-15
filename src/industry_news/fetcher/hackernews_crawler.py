from datetime import datetime
import logging
from bs4 import BeautifulSoup
from typing import List, Optional, Tuple
from requests.models import Response
import re
from urllib.parse import urljoin, urlparse, ParseResult
from industry_news.article import SOURCE, ArticleMetadata
from industry_news.fetcher.fetcher import (
    CONTINUE_PAGINATING,
    Fetcher,
)
from industry_news.fetcher.web_tools import verify_page_element
from industry_news.utils import delay_random
from .web_tools import DELAY_RANGE_S, construct_url, get_with_retries
from bs4.element import Tag


LOGGER = logging.getLogger(__name__)
BASE_URL: str = "https://news.ycombinator.com"
SITE_LINK: ParseResult = construct_url(BASE_URL, "newest")


class HackerNewsCrawler(Fetcher):

    def __init__(self, site_link: ParseResult = SITE_LINK) -> None:
        super().__init__()
        self._site_link = site_link  # Possible to pass other sorting orders

    def articles_metadata(
        self, since: datetime, until: datetime = datetime.now()
    ) -> List[ArticleMetadata]:
        articles_metadata: List[ArticleMetadata] = []
        page_link: Optional[ParseResult] = self._site_link

        while page_link:
            LOGGER.info(
                "Fetching articles from HackerNews: %s", page_link.geturl()
            )
            response: Response = get_with_retries(url=page_link)
            soup: BeautifulSoup = BeautifulSoup(
                response.content, "html.parser"
            )
            retrieved_metadata: List[ArticleMetadata]
            paginating: CONTINUE_PAGINATING

            retrieved_metadata, paginating = (
                HackerNewsCrawler._extract_articles_from_page(
                    soup=soup, since=since, until=until
                )
            )

            articles_metadata.extend(retrieved_metadata)

            if CONTINUE_PAGINATING.STOP == paginating:
                break

            page_link = self._next_page_link(soup=soup)
            delay_random(DELAY_RANGE_S)

        return articles_metadata

    @staticmethod
    def _extract_articles_from_page(
        soup: BeautifulSoup, since: datetime, until: datetime
    ) -> Tuple[List[ArticleMetadata], CONTINUE_PAGINATING]:
        urls: List[ArticleMetadata] = []
        paginating: CONTINUE_PAGINATING = CONTINUE_PAGINATING.CONTINUE

        for row in soup.find_all("tr", class_="athing"):
            title_row: Tag = verify_page_element(row, Tag)
            title_span: Tag = verify_page_element(
                title_row.find("span", class_="titleline"), Tag
            )

            if title_span:
                if (
                    HackerNewsCrawler._process_title_row(
                        title_span=title_span,
                        title_row=title_row,
                        urls=urls,
                        since=since,
                        until=until,
                    )
                    == CONTINUE_PAGINATING.STOP
                ):
                    return urls, CONTINUE_PAGINATING.STOP

        return urls, paginating

    @staticmethod
    def _process_title_row(
        title_span: Tag,
        title_row: Tag,
        urls: List[ArticleMetadata],
        since: datetime,
        until: datetime,
    ) -> CONTINUE_PAGINATING:
        article_metadata: ArticleMetadata = (
            HackerNewsCrawler._single_article_metadata(
                title_span=title_span, title_row=title_row
            )
        )

        if article_metadata.publication_date > until:
            return CONTINUE_PAGINATING.CONTINUE
        elif until >= article_metadata.publication_date >= since:
            urls.append(article_metadata)
            return CONTINUE_PAGINATING.CONTINUE
        else:
            return CONTINUE_PAGINATING.STOP

    @staticmethod
    def _single_article_metadata(
        title_span: Tag, title_row: Tag
    ) -> ArticleMetadata:
        return ArticleMetadata(
            url=HackerNewsCrawler._single_article_url(title_span),
            title=HackerNewsCrawler._single_article_title(title_span),
            source=SOURCE.HACKER_NEWS,
            publication_date=HackerNewsCrawler._single_article_publication_date(
                title_row
            ),
            score=HackerNewsCrawler._single_article_score(title_row),
        )

    @staticmethod
    def _single_article_title(title_span: Tag) -> str:
        link_tag: Tag = verify_page_element(title_span.find("a"), Tag)
        return verify_page_element(link_tag.get_text(), str)

    @staticmethod
    def _single_article_url(title_span: Tag) -> ParseResult:
        link_tag: Tag = verify_page_element(title_span.find("a"), Tag)
        link: str = verify_page_element(link_tag["href"], str)
        absolute_link: str = (
            link if link.startswith("http") else urljoin(BASE_URL, link)
        )
        return urlparse(absolute_link)

    @staticmethod
    def _single_article_publication_date(row: Tag) -> datetime:
        date_span: Tag = HackerNewsCrawler._span_from_next_row(row, "age")
        publication_date: str = verify_page_element(date_span["title"], str)
        return datetime.strptime(publication_date, "%Y-%m-%dT%H:%M:%S")

    @staticmethod
    def _single_article_score(row: Tag) -> int:
        score_span: Tag = HackerNewsCrawler._span_from_next_row(row, "score")
        score: str = verify_page_element(score_span.get_text(), str)
        match = re.search(r"\d+", score)

        if match:
            return int(match.group())
        else:
            raise ValueError("Couldn't parse the score.")

    @staticmethod
    def _span_from_next_row(row: Tag, class_: str) -> Tag:
        next_row: Tag = verify_page_element(row.find_next_sibling("tr"), Tag)
        return verify_page_element(next_row.find("span", class_=class_), Tag)

    def _next_page_link(self, soup: BeautifulSoup) -> Optional[ParseResult]:
        more_link_tag: Tag = verify_page_element(
            soup.find("a", text="More"), Tag
        )
        more_link: str = verify_page_element(more_link_tag["href"], str)
        return (
            urlparse(urljoin(self._site_link.geturl(), more_link))
            if more_link
            else None
        )
