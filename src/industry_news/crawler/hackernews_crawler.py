from datetime import datetime
from enum import Enum
from bs4 import BeautifulSoup
from typing import List, Optional, Tuple
from requests.models import Response
from urllib.parse import urljoin, urlparse, ParseResult
from industry_news.crawler.web_tools import verify_page_element
from industry_news.utils import delay_random
from .web_tools import DELAY_RANGE, get_with_retries
from bs4.element import Tag, NavigableString

PageElement = Tag | NavigableString

BASE_URL: str = "https://news.ycombinator.com"
SITE_LINK: ParseResult = urlparse(urljoin(BASE_URL, "newest"))


class CONTINUE_PAGINATING(Enum):
    CONTINUE = True
    STOP = False


def articles(since: datetime, until: datetime = datetime.now()) -> List[str]:
    article_urls: List[str] = []
    page_link: Optional[ParseResult] = SITE_LINK

    while page_link:
        response: Response = get_with_retries(url=page_link)
        soup: BeautifulSoup = BeautifulSoup(response.content, "html.parser")
        retrieved_urls: List[str]
        paginating: CONTINUE_PAGINATING

        retrieved_urls, paginating = _article_urls(
            soup=soup, since=since, until=until
        )

        article_urls.extend(retrieved_urls)

        if CONTINUE_PAGINATING.STOP == paginating:
            break

        page_link = _next_page_link(soup=soup)
        delay_random(DELAY_RANGE)

    return article_urls


def _article_urls(
    soup: BeautifulSoup, since: datetime, until: datetime
) -> Tuple[List[str], CONTINUE_PAGINATING]:
    urls: List[str] = []
    paginating: CONTINUE_PAGINATING = CONTINUE_PAGINATING.CONTINUE

    for row in soup.find_all("tr", class_="athing"):
        title_row: Tag = verify_page_element(row, Tag)
        title_span: Tag = verify_page_element(
            title_row.find("span", class_="titleline"), Tag
        )

        if title_span:
            if (
                _process_title(
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


def _process_title(
    title_span: Tag,
    title_row: Tag,
    urls: List[str],
    since: datetime,
    until: datetime,
) -> CONTINUE_PAGINATING:
    link: str = _single_article_url(title_span)
    publication_date: datetime = _single_article_publication_date(title_row)

    if publication_date > until:
        return CONTINUE_PAGINATING.CONTINUE
    elif publication_date >= since and publication_date <= until:
        urls.append(link)
        return CONTINUE_PAGINATING.CONTINUE
    else:
        return CONTINUE_PAGINATING.STOP


def _single_article_url(title_span: Tag) -> str:
    link_tag: Tag = verify_page_element(title_span.find("a"), Tag)
    link: str = verify_page_element(link_tag["href"], str)
    return link if link.startswith("http") else urljoin(BASE_URL, link)


def _single_article_publication_date(row: Tag) -> datetime:
    next_row: Tag = verify_page_element(row.find_next_sibling("tr"), Tag)
    date_span: Tag = verify_page_element(
        next_row.find("span", class_="age"), Tag
    )
    publication_date: str = verify_page_element(date_span["title"], str)
    return datetime.strptime(publication_date, "%Y-%m-%dT%H:%M:%S")


def _next_page_link(soup: BeautifulSoup) -> Optional[ParseResult]:
    more_link_tag: Tag = verify_page_element(soup.find("a", text="More"), Tag)
    more_link: str = verify_page_element(more_link_tag["href"], str)
    return (
        urlparse(urljoin(SITE_LINK.geturl(), more_link)) if more_link else None
    )
