import requests
from bs4 import BeautifulSoup
from typing import List, Tuple
import random
import time

USER_AGENT: str = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"
)
RETRIES: int = 3
DELAY_RANGE: Tuple[int, int] = (1, 5)


def fetch_articles(site_link: str, element_class: str) -> List[str]:
    response: requests.Response = _make_request_with_retries(url=site_link)
    soup: BeautifulSoup = BeautifulSoup(response.content, "html.parser")
    urls: List[str] = _get_article_urls(soup=soup, element_class=element_class)

    articles: List[str] = [
        _fetch_article_text(site_link=site_link, article_link=article_link)
        for article_link in urls
    ]

    return articles


def _make_request_with_retries(url: str) -> requests.Response:
    for _ in range(RETRIES):
        try:
            headers: dict = {"User-Agent": USER_AGENT}
            response: requests.Response = requests.get(
                url=url, headers=headers
            )
            return response
        except requests.RequestException:
            delay: float = random.uniform(DELAY_RANGE[0], DELAY_RANGE[1])
            time.sleep(delay)
    return requests.Response()


def _get_article_urls(soup: BeautifulSoup, element_class: str) -> List[str]:
    list_elements: List[BeautifulSoup] = soup.find_all(
        "span", class_=element_class
    )
    urls: List[str] = [
        element.find("a")["href"]
        for element in list_elements
        if element.find("a")
    ]
    return urls


def _fetch_article_text(
    site_link: str,
    article_link: str,
    retries: int,
    delay_range: Tuple[int, int],
) -> str:
    if article_link.startswith("http"):
        article_response: requests.Response = _make_request_with_retries(
            url=article_link, retries=retries, delay_range=delay_range
        )
    else:
        article_response: requests.Response = _make_request_with_retries(
            url=site_link + article_link,
            retries=retries,
            delay_range=delay_range,
        )
    article_soup: BeautifulSoup = BeautifulSoup(
        article_response.content, "html.parser"
    )
    article_text: str = article_soup.get_text()
    return article_text


if __name__ == "__main__":
    site_link: str = "https://news.ycombinator.com/"
    list_element_name: str = "titleline"

    articles: List[str] = fetch_articles(
        site_link=site_link, element_class=list_element_name
    )
    print(articles[0])
