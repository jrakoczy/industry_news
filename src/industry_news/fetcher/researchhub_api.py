from datetime import datetime
import logging
from typing import Any, List, Optional
from urllib.parse import ParseResult, urlparse
import requests
from industry_news.digest.article import ArticleSummary, ArticleMetadata
from industry_news.fetcher.fetcher import (
    CONTINUE_PAGINATING,
    Source,
    SummaryFetcher,
)
from industry_news.fetcher.web_tools import (
    DELAY_RANGE_S,
    construct_url,
    get_with_retries,
    modify_url_query,
)
from industry_news.utils import delay_random


class ResearchHubApi(SummaryFetcher):

    _LOGGER = logging.getLogger(__name__)
    _SITE_POST_URL: ParseResult = urlparse(
        "https://www.researchhub.com/paper/"
    )
    _BASE_API_URL: str = "https://backend.researchhub.com/api/"
    _SITE_LINK: ParseResult = construct_url(
        base_url=_BASE_API_URL,
        relative_path="researchhub_unified_document/get_unified_documents/",
        query_params={"ordering": "new", "time": "all", "type": "all"},
    )

    def __init__(
        self,
        site_post_url: ParseResult = _SITE_POST_URL,
        site_link: ParseResult = _SITE_LINK,
    ):
        self._site_post_url: ParseResult = site_post_url
        self._site_link: ParseResult = site_link

    @staticmethod
    def source() -> Source:
        return Source.RESEARCH_HUB

    def subspace(self) -> Optional[str]:
        return None

    def article_summaries(
        self, since: datetime, until: datetime
    ) -> List[ArticleSummary]:

        page: int = 1
        articles: List[ArticleSummary] = []
        paginating: CONTINUE_PAGINATING = CONTINUE_PAGINATING.CONTINUE
        response: requests.Response = get_with_retries(self._site_link)

        while paginating == CONTINUE_PAGINATING.CONTINUE:
            self._LOGGER.info(
                "Fetching articles from ResearchHub, page: %d", page
            )

            data: Any = response.json()
            posts: List[Any] = data.get("results", [])

            paginating = self._process_results_page(
                since, until, articles, posts
            )

            page += 1
            response = self._fetch_page_with_delay(page)
            if response.status_code == 404:
                paginating = CONTINUE_PAGINATING.STOP

        return articles

    def _fetch_page_with_delay(self, page: int) -> requests.Response:
        site_link = modify_url_query(self._site_link, {"page": str(page)})
        delay_random(DELAY_RANGE_S)
        return get_with_retries(site_link)

    def _process_results_page(
        self,
        since: datetime,
        until: datetime,
        articles: List[ArticleSummary],
        posts: List[Any],
    ) -> CONTINUE_PAGINATING:
        for post in posts:
            metadata: Optional[ArticleMetadata] = (
                self._single_article_metadata(post)
            )
            paginating: CONTINUE_PAGINATING = CONTINUE_PAGINATING.CONTINUE

            if metadata is None:  # Skip non-article posts
                continue
            if metadata.publication_date < since:
                paginating = CONTINUE_PAGINATING.STOP
                break
            if until >= metadata.publication_date >= since:
                articles.append(
                    ArticleSummary(
                        metadata=metadata,
                        summary=post["documents"]["abstract"],
                    )
                )

        return paginating

    def _single_article_metadata(self, post: Any) -> Optional[ArticleMetadata]:
        metadata: Optional[ArticleMetadata] = None

        if isinstance(post["documents"], dict):  # Ignore non-article posts
            publication_date: datetime = datetime.strptime(
                post["created_date"], "%Y-%m-%dT%H:%M:%S.%fZ"
            )
            metadata = ArticleMetadata(
                title=post["documents"]["title"],
                source=Source.RESEARCH_HUB,
                url=self._single_article_url(post),
                publication_date=publication_date,
                score=post["score"],
            )

        return metadata

    def _single_article_url(self, post: Any) -> ParseResult:
        document: Any = post["documents"]
        if post["documents"]["pdf_copyright_allows_display"]:
            return urlparse(document["file"])
        else:
            return construct_url(
                self._site_post_url.geturl(),
                f"{document['id']}/{document['slug']}",
            )
