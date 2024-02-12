from datetime import datetime
from bs4 import BeautifulSoup
from typing import List, Optional, Tuple
from requests.models import Response
from urllib.parse import urljoin
from crawler.http_tools import get_with_retries
from utils import fail_gracefully


BASE_URL: str = "https://news.ycombinator.com"
SITE_LINK: str = urljoin(BASE_URL, "newest")
LIST_ELEMENT_CLASS: str = "titleline"


def articles(since: datetime) -> List[str]:
    articles: List[str] = []
    page_link: Optional[str] = SITE_LINK

    while page_link:
        response: Response = get_with_retries(url=page_link)
        soup: BeautifulSoup = BeautifulSoup(response.content, "html.parser")
        urls: List[str]
        shouldTerminate: bool
        urls, shouldTerminate = _article_urls(soup=soup, since=since)

        articles.extend(_articles_texts(urls))

        if shouldTerminate:
            break

        page_link = _next_page_link(soup=soup)

    return articles


def _article_urls(
    soup: BeautifulSoup, since: datetime
) -> Tuple[List[str], bool]:
    urls: List[str] = []
    shouldTerminate: bool = False

    for row in soup.find_all("tr", class_="athing"):
        title_span: Optional[BeautifulSoup] = row.find(
            "span", class_=LIST_ELEMENT_CLASS
        )
        if title_span:
            link: str = _single_article_url(title_span)
            publication_date: datetime = _single_article_publication_date(row)

            if publication_date > since:
                urls.append(link)
            else:
                shouldTerminate = True
                break

    return urls, shouldTerminate


def _single_article_url(title_span: BeautifulSoup) -> str:
    link: str = title_span.find("a")["href"]
    return link if link.startswith("http") else urljoin(BASE_URL, link)


def _single_article_publication_date(row: BeautifulSoup) -> datetime:
    next_row: Optional[BeautifulSoup] = row.find_next_sibling("tr")
    publication_date: str = next_row.find("span", class_="age")["title"]
    return datetime.strptime(publication_date, "%Y-%m-%dT%H:%M:%S")


def _articles_texts(urls: List[str]) -> List[str]:
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
