from crawler.http_tools import get_with_retries
from utils import fail_gracefully

from bs4 import BeautifulSoup
from typing import List, Optional
from requests.models import Response

SITE_LINK: str = "https://news.ycombinator.com/"
LIST_ELEMENT_CLASS: str = "titleline"


def articles() -> List[str]:
    response: Response = get_with_retries(url=SITE_LINK)
    soup: BeautifulSoup = BeautifulSoup(response.content, "html.parser")
    urls: List[str] = _article_urls(soup=soup)

    articles: List[str] = [
        text
        for article_link in urls
        if (text := _single_article_text(article_link)) is not None
    ]

    return articles


def _article_urls(soup: BeautifulSoup) -> List[str]:
    list_elements: List[BeautifulSoup] = soup.find_all(
        "span", class_=LIST_ELEMENT_CLASS
    )
    urls: List[str] = [
        found["href"]
        for element in list_elements
        if (found := element.find("a"))
    ]
    return urls


def _single_article_text(article_link: str) -> Optional[str]:
    response: Optional[Response] = _send_request(article_link)
    return _retrieve_text(response) if response is not None else None


def _send_request(article_link: str) -> Optional[Response]:
    url: str = (
        SITE_LINK + article_link
        if not article_link.startswith("http")
        else article_link
    )
    article_response: Response = fail_gracefully(lambda: get_with_retries(url))
    return article_response


def _retrieve_text(response: Response) -> Optional[str]:
    soup: BeautifulSoup = BeautifulSoup(response.content, "html.parser")
    return fail_gracefully(soup.get_text)
