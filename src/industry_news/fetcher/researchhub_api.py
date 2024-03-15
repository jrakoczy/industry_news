from datetime import datetime
import logging
from re import S
from typing import Any, List, Optional
from urllib.parse import ParseResult, urlparse
import requests
from industry_news.article import SOURCE, Article, ArticleMetadata
from industry_news.fetcher.fetcher import (
    CONTINUE_PAGINATING,
)
from industry_news.fetcher.web_tools import (
    DELAY_RANGE_S,
    construct_url,
    get_with_retries,
    modify_url_query,
)
from industry_news.utils import delay_random

LOGGER = logging.getLogger(__name__)
SITE_POST_URL = "https://www.researchhub.com/paper/"
BASE_API_URL: str = "https://backend.researchhub.com/api/"
PAGE_LINK: ParseResult = construct_url(
    base_url=BASE_API_URL,
    relative_path="researchhub_unified_document/get_unified_documents/",
    query_params={"ordering": "new", "time": "all", "type": "all"},
)


class ResearchHubApi:

    def articles(
        self, since: datetime, until: datetime = datetime.now()
    ) -> List[Article]:

        page: int = 1
        articles: List[Article] = []
        paginating: CONTINUE_PAGINATING = CONTINUE_PAGINATING.CONTINUE
        response: requests.Response = get_with_retries(PAGE_LINK)

        while paginating == CONTINUE_PAGINATING.CONTINUE:
            LOGGER.info("Fetching articles from ResearchHub, page: %d", page)

            data: Any = response.json()
            posts: List[Any] = data.get("results", [])

            paginating = ResearchHubApi._process_results_page(
                since, until, articles, posts
            )

            page += 1
            response = ResearchHubApi._fetch_page_with_delay(page)
            if response.status_code == 404:
                paginating = CONTINUE_PAGINATING.STOP

        return articles

    @staticmethod
    def _fetch_page_with_delay(page: int) -> requests.Response:
        site_link = modify_url_query(PAGE_LINK, {"page": str(page)})
        delay_random(DELAY_RANGE_S)
        return get_with_retries(site_link)

    @staticmethod
    def _process_results_page(
        since: datetime,
        until: datetime,
        articles: List[Article],
        posts: List[Any],
    ) -> CONTINUE_PAGINATING:
        for post in posts:
            metadata: Optional[ArticleMetadata] = (
                ResearchHubApi._single_article_metadata(post)
            )
            paginating: CONTINUE_PAGINATING = CONTINUE_PAGINATING.CONTINUE

            if metadata is None:  # Skip non-article posts
                continue
            if metadata.publication_date < since:
                paginating = CONTINUE_PAGINATING.STOP
                break
            if until >= metadata.publication_date >= since:
                articles.append(
                    Article(
                        metadata=metadata,
                        summary=post["documents"]["abstract"],
                    )
                )

        return paginating

    @staticmethod
    def _single_article_metadata(post: Any) -> Optional[ArticleMetadata]:
        metadata: Optional[ArticleMetadata] = None

        if isinstance(post["documents"], dict):  # Ignore non-article posts
            publication_date: datetime = datetime.strptime(
                post["created_date"], "%Y-%m-%dT%H:%M:%S.%fZ"
            )
            metadata = ArticleMetadata(
                title=post["documents"]["title"],
                source=SOURCE.RESEARCH_HUB,
                url=ResearchHubApi._single_article_url(post),
                publication_date=publication_date,
                score=post["score"],
            )

        return metadata

    @staticmethod
    def _single_article_url(post: Any) -> ParseResult:
        document: Any = post["documents"]
        if post["documents"]["pdf_copyright_allows_display"]:
            return urlparse(document["file"])
        else:
            return construct_url(
                SITE_POST_URL, f"{document['id']}/{document['slug']}"
            )
