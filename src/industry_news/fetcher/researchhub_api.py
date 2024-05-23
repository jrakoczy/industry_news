from datetime import datetime, timezone
import logging
from pathlib import Path
from typing import Any, List, Optional
from urllib.parse import ParseResult, urlparse
from industry_news.config import load_config
from industry_news.digest.article import ArticleSummary, ArticleMetadata
from industry_news.sources import Source
from industry_news.fetcher.fetcher import (
    CONTINUE_PAGINATING,
    SummaryFetcher,
)
from industry_news.fetcher.web_tools import (
    construct_url,
    get_json_with_backup,
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
        data_backup_path: Path = load_config().output.digest
        / "data"
        / "researchhub",
    ):
        self._site_post_url: ParseResult = site_post_url
        self._site_link: ParseResult = site_link
        self._data_backup_path = data_backup_path

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
        data: dict[str, Any] = get_json_with_backup(
            self._site_link,
            self._page_to_filepath(since=since, until=until, page=0),
        )

        while paginating == CONTINUE_PAGINATING.CONTINUE:
            self._LOGGER.info(
                "Fetching articles from ResearchHub, page: %d", page
            )

            posts: List[Any] = data.get("results", [])

            paginating = self._process_results_page(
                since, until, articles, posts
            )

            page += 1
            data = self._fetch_page_with_delay(
                page,
                self._page_to_filepath(since=since, until=until, page=page),
            )

        return articles

    def _fetch_page_with_delay(
        self, page: int, filepath: Path
    ) -> dict[str, Any]:
        site_link = modify_url_query(self._site_link, {"page": str(page)})
        delay_random(delay_range_s=(0.5, 1.0))
        data: dict[str, Any] = get_json_with_backup(site_link, filepath)
        return data

    def _page_to_filepath(
        self, since: datetime, until: datetime, page: int
    ) -> Path:
        filename = f"{since.isoformat()}-{until.isoformat()}-{page}.json"
        return self._data_backup_path / filename

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
            if metadata.publication_date_utc < since:
                paginating = CONTINUE_PAGINATING.STOP
                break
            if until >= metadata.publication_date_utc >= since:
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
            ).replace(tzinfo=timezone.utc)
            metadata = ArticleMetadata(
                title=post["documents"]["title"],
                source=Source.RESEARCH_HUB,
                url=self._single_article_url(post),
                publication_date_utc=publication_date,
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
