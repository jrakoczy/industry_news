from datetime import datetime
from enum import Enum
import logging
from bs4 import BeautifulSoup
from typing import List, Optional, Tuple, Type, TypeVar
from requests.models import Response
from urllib.parse import urljoin
from .http_tools import get_with_retries
from industry_news.utils import fail_gracefully
from bs4.element import Tag, NavigableString

PageElement = Tag | NavigableString

LOGGER = logging.getLogger(__name__)
BASE_URL: str = "https://news.ycombinator.com"
SITE_LINK: str = urljoin(BASE_URL, "newest")

T = TypeVar("T")
R = TypeVar("R")


class CONTINUE_PAGINATING(Enum):
    CONTINUE = True
    STOP = False


def articles(since: datetime, until: datetime = datetime.now()) -> List[str]:
    articles: List[str] = []
    page_link: Optional[str] = SITE_LINK

    while page_link:
        response: Response = get_with_retries(url=page_link)
        soup: BeautifulSoup = BeautifulSoup(response.content, "html.parser")
        urls: List[str]
        paginating: CONTINUE_PAGINATING

        urls, paginating = _retrieve_urls(
            soup=soup, since=since, until=until
        )

        articles.extend(_articles_texts(urls))

        if CONTINUE_PAGINATING.STOP == paginating:
            break

        page_link = _next_page_link(soup=soup)

    return articles


def _retrieve_urls(
    soup: BeautifulSoup, since: datetime, until: datetime
) -> Tuple[List[str], CONTINUE_PAGINATING]:
    urls: List[str] = []
    paginating: CONTINUE_PAGINATING = CONTINUE_PAGINATING.CONTINUE

    for row in soup.find_all("tr", class_="athing"):
        title_row: Tag = _verify_element(row, Tag)
        title_span: Tag = _verify_element(
            title_row.find("span", class_="titleline"), Tag
        )

        if title_span:
            if _process_title(
                title_span=title_span,
                title_row=title_row,
                urls=urls,
                since=since,
                until=until
            ) == CONTINUE_PAGINATING.STOP:
                return urls, CONTINUE_PAGINATING.STOP

    return urls, paginating


def _process_title(
    title_span: Tag,
    title_row: Tag,
    urls: List[str],
    since: datetime,
    until: datetime
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
    link_tag: Tag = _verify_element(title_span.find("a"), Tag)
    link: str = _verify_element(link_tag["href"], str)
    return link if link.startswith("http") else urljoin(BASE_URL, link)


def _single_article_publication_date(row: Tag) -> datetime:
    next_row: Tag = _verify_element(row.find_next_sibling("tr"), Tag)
    date_span: Tag = _verify_element(next_row.find("span", class_="age"), Tag)
    publication_date: str = _verify_element(date_span["title"], str)
    return datetime.strptime(publication_date, "%Y-%m-%dT%H:%M:%S")


def _articles_texts(urls: List[str]) -> List[str]:
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


def _send_request(url: str) -> Optional[Response]:
    LOGGER.info(f"Retrieving article from {url}")
    response: Optional[Response] = fail_gracefully(
        lambda: get_with_retries(url)
    )
    return response


def _retrieve_text(response: Response) -> Optional[str]:
    soup: BeautifulSoup = BeautifulSoup(response.content, "html.parser")
    return fail_gracefully(soup.get_text)


def _next_page_link(soup: BeautifulSoup) -> Optional[str]:
    more_link_tag: Tag = _verify_element(soup.find("a", text="More"), Tag)
    more_link: str = _verify_element(more_link_tag["href"], str)
    return urljoin(SITE_LINK, more_link) if more_link else None


def _verify_element(element: Optional[T], type_: Type[R]) -> R:
    if not isinstance(element, type_):
        raise ValueError("Invalid page element.")
    return element
