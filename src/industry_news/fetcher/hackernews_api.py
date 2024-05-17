import logging
from datetime import datetime
from typing import Any, List, Optional
from urllib.parse import ParseResult, urlparse
from pydantic import BaseModel, validator
from industry_news.digest.article import ArticleMetadata
from industry_news.fetcher.fetcher import MetadataFetcher
from industry_news.fetcher.web_tools import get_with_retries
from industry_news.sources import Source
from industry_news.utils import fail_gracefully


class HackerNewsItem(BaseModel):
    by: str
    descendants: int
    id: int
    kids: Optional[List[int]]
    score: int
    text: Optional[str]
    time: datetime
    title: str
    type: str
    url: str

    @validator("time", pre=True)
    def convert_epoch_to_datetime(cls, value: int) -> datetime:
        if isinstance(value, int):
            return datetime.fromtimestamp(value)
        else:
            raise ValueError("`time` is not an int")


class HackerNewsApi(MetadataFetcher):
    _LOGGER = logging.getLogger(__name__)
    _API_BASE_URL = "https://hacker-news.firebaseio.com/v0"
    _MAX_CONSECUTIVE_ERRORS = 4

    @staticmethod
    def source() -> Source:
        return Source.HACKER_NEWS

    def subspace(self) -> Optional[str]:
        return None

    def articles_metadata(
        self, since: datetime, until: datetime
    ) -> List[ArticleMetadata]:
        articles_metadata: List[ArticleMetadata] = []
        max_item_id = self._get_max_item_id()
        item_id = max_item_id
        errors_cnt = 0

        # Have checks in place to not send more than _MAX_POSTS requests
        # in case of error responses.
        while item_id > 0:
            item: Optional[HackerNewsItem] = fail_gracefully(
                lambda: self._get_item(item_id)
            )

            if item is not None:
                if self._is_story_within_range(item, since=since, until=until):
                    articles_metadata.append(
                        self._single_article_metadata(item)
                    )
                elif item.time < since:
                    break
            else:
                errors_cnt += 1
                HackerNewsApi._raise_if_too_many_failed(errors_cnt)

            item_id -= 1

        return articles_metadata

    def _get_max_item_id(self) -> int:
        url: ParseResult = urlparse("{self._API_BASE_URL}/maxitem.json")
        response = get_with_retries(url)
        return int(response.json())

    def _get_item(self, item_id: int) -> HackerNewsItem:
        url: ParseResult = urlparse("{self._API_BASE_URL}/item/{item_id}.json")
        item_data: dict[str, Any] = get_with_retries(url).json()

        # Add an url is it's a Hackernews post (not an external one).
        if "url" not in item_data:
            item_data["url"] = url
        return HackerNewsItem(**item_data)

    def _is_story_within_range(
        self, item: HackerNewsItem, since: datetime, until: datetime
    ) -> bool:
        return since <= item.time <= until and item.type == "story"

    @classmethod
    def _raise_if_too_many_failed(cls, errors_cnt: int) -> None:
        if errors_cnt > cls._MAX_CONSECUTIVE_ERRORS:
            raise Exception(
                f"More than {cls._MAX_CONSECUTIVE_ERRORS} consecutive"
                + "missed items."
            )

    def _single_article_metadata(
        self, item: HackerNewsItem
    ) -> ArticleMetadata:
        return ArticleMetadata(
            url=urlparse(item.url),
            title=item.title,
            source=Source.HACKER_NEWS,
            publication_date_utc=item.time,
            score=item.score,
        )
