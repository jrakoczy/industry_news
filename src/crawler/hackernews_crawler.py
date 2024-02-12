from crawler.http_tools import get_with_retries
from utils import fail_gracefully

from bs4 import BeautifulSoup
from typing import List, Optional
from requests.models import Response
from urllib.parse import urljoin


SITE_LINK: str = "https://news.ycombinator.com/"
LIST_ELEMENT_CLASS: str = "titleline"


def articles() -> List[str]:
    articles: List[str] = []

    page_link: Optional[str] = SITE_LINK
    while page_link:
        response: Response = get_with_retries(url=page_link)
        soup: BeautifulSoup = BeautifulSoup(response.content, "html.parser")
        urls: List[str] = _article_urls(soup=soup)

        articles.extend(_article_texts(urls))

        page_link = _next_page_link(soup=soup)

    return articles


def _article_urls(soup: BeautifulSoup) -> List[str]:
    list_items: List[BeautifulSoup] = soup.find_all(
        "span", class_=LIST_ELEMENT_CLASS
    )
    urls: List[str] = [
        found
        for element in list_items
        if element.find("a") and (found := element.find("a").get("href"))
    ]
    urls = [
        url if url.startswith("http") else urljoin(SITE_LINK, url)
        for url in urls
    ]
    return urls


def _article_texts(urls: List[str]) -> List[str]:
    article_texts: List[str] = []
    for url in urls:
        response: Optional[Response] = _send_request(url)
        if response is not None:
            article_texts.append(_retrieve_text(response))
    return article_texts


def _send_request(url: str) -> Optional[Response]:
    response: Response = fail_gracefully(lambda: get_with_retries(url))
    return response


def _retrieve_text(response: Response) -> str:
    soup: BeautifulSoup = BeautifulSoup(response.content, "html.parser")
    return fail_gracefully(soup.get_text)


def _next_page_link(soup: BeautifulSoup) -> Optional[str]:
    more_link: Optional[BeautifulSoup] = soup.find("a", text="More")
    return urljoin(SITE_LINK, more_link["href"]) if more_link else None
