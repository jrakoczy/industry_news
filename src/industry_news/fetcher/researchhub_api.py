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
    get_with_retries,
    modify_url_query,
)
from industry_news.utils import delay_random, from_file_backup


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
        data_backup_path: Path = load_config().digest.out_path
        / "data"
        / "researchhub",
        load_data_from_backup: bool = False,
    ):
        """
        Args:
            load_data_from_backup (bool, optional): _description_. Defaults to
            False. If set to True, the data will be loaded from a dir specified
            in py:attr:_data_backup_path. It will ONLY work if this data set
            contains all required ResearchHub pages, it is not possible to fall
            back to requests to the Research Hub API in case of missing files.
            They use ascending natural numbers as pagination parameters
            means a contant of every page is different each time you fetch it
            with the same parameter value.

            It still useful to use backup files if the whole retrieval process
            succeeded, but the code failed at some later stage when analyzing
            the data.
        """
        self._site_post_url: ParseResult = site_post_url
        self._site_link: ParseResult = site_link
        self._data_backup_path = data_backup_path
        self._load_data_from_backup = load_data_from_backup

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

        while paginating == CONTINUE_PAGINATING.CONTINUE:
            data: dict[str, Any] = self._fetch_page_with_delay(page)
            self._LOGGER.info(
                "Fetching articles from ResearchHub, page: %d", page
            )

            posts: List[Any] = data.get("results", [])

            paginating = self._process_results_page(
                since, until, articles, posts
            )

            page += 1

        return articles

    def _fetch_page_with_delay(self, page: int) -> dict[str, Any]:
        delay_random(delay_range_s=(0.5, 1.0))
        data: dict[str, Any] = self._get_page_data(page)
        return data

    def _get_page_data(self, page: int) -> dict[str, Any]:
        """See :py:meth:~.__init__ 's comment."""
        data: dict[str, Any]

        if self._load_data_from_backup:
            data = self._get_data_from_backup(page)
        else:
            site_link = modify_url_query(self._site_link, {"page": str(page)})
            data = get_with_retries(site_link).json()

        return data

    def _get_data_from_backup(self, page: int) -> dict[str, Any]:
        data_from_file: Optional[dict[str, Any]] = from_file_backup(
            self._page_to_filepath(page)
        )
        if not data_from_file:
            raise FileNotFoundError(
                f"Can't load Research hub page {page} from backup files."
            )

        return data_from_file

    def _page_to_filepath(self, page: int) -> Path:
        filename = f"{page}.json"
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
