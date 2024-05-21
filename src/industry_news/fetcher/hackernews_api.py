import logging
from datetime import datetime, timedelta, timezone
from typing import Any, List, Optional, Union
from urllib.parse import ParseResult, urlparse
from pydantic import BaseModel, validator
from industry_news.digest.article import ArticleMetadata
from industry_news.fetcher.fetcher import MetadataFetcher
from industry_news.fetcher.web_tools import get_with_retries
from industry_news.sources import Source
from industry_news.utils import to_utc_datetime


class HackerNewsStory(BaseModel):
    by: str
    id: int
    score: int
    text: Optional[str] = None
    time: datetime
    title: str
    type: str
    url: str

    @validator("time", pre=True)
    def convert_epoch_to_datetime(cls, value: int) -> datetime:
        if isinstance(value, int):
            return to_utc_datetime(value)
        else:
            raise ValueError("`time` is not an int")


class HackerNewsApi(MetadataFetcher):
    _LOGGER = logging.getLogger(__name__)
    _API_BASE_URL = "https://hacker-news.firebaseio.com/v0"
    _MAX_JUMP_SIZE = 2000

    @staticmethod
    def source() -> Source:
        return Source.HACKER_NEWS

    def subspace(self) -> Optional[str]:
        return None

    def articles_metadata(
        self, since: datetime, until: datetime
    ) -> List[ArticleMetadata]:
        articles_metadata: List[ArticleMetadata] = []
        item_id = self._get_max_item_id()

        while item_id > 0:
            item: Union[HackerNewsStory, datetime] = self._get_story(item_id)
            time: datetime = item if isinstance(item, datetime) else item.time

            if isinstance(item, HackerNewsStory):
                if until <= time <= since:
                    articles_metadata.append(
                        self._single_article_metadata(item)
                    )

            if time < since:
                break

            item_id -= HackerNewsApi._jump_size(current_time=time, until=until)

        return articles_metadata

    def _get_max_item_id(self) -> int:
        url: ParseResult = urlparse(f"{self._API_BASE_URL}/maxitem.json")
        response = get_with_retries(url)
        return int(response.json())

    def _get_story(self, item_id: int) -> Union[HackerNewsStory, datetime]:
        url: ParseResult = urlparse(
            f"{self._API_BASE_URL}/item/{item_id}.json"
        )
        item_data: dict[str, Any] = get_with_retries(url).json()
        publication_date: datetime = to_utc_datetime(item_data["time"])

        logging.info(f"[Hackernews] {url.geturl()} -- {publication_date}")

        if item_data["type"] == "story" and HackerNewsApi._is_alive(item_data):
            return HackerNewsApi._data_to_story(item_data, url)
        else:
            return publication_date

    @classmethod
    def _jump_size(cls, current_time: datetime, until: datetime) -> int:
        """
        Make larger jumps the further in time we are after `until`.

        Returns:
            int: a number of items to be skipped - 1
        """
        time_diff: timedelta = current_time - until
        minutes = int(time_diff.total_seconds() / 60)
        return min(max(1, minutes), cls._MAX_JUMP_SIZE)

    @staticmethod
    def _is_alive(item_data: dict[str, Any]) -> bool:
        dead = "dead"
        deleted = "deleted"
        return HackerNewsApi._is_field_not_true(
            item_data, dead
        ) and HackerNewsApi._is_field_not_true(item_data, deleted)

    @staticmethod
    def _is_field_not_true(item_data: dict[str, Any], key: str) -> bool:
        return not (key in item_data and item_data[key] is True)

    @staticmethod
    def _data_to_story(
        item_data: dict[str, Any], url: ParseResult
    ) -> HackerNewsStory:
        # Add an url is it's a Hackernews post (not an external one).
        if "url" not in item_data:
            item_data["url"] = url.geturl()
        return HackerNewsStory(**item_data)

    def _single_article_metadata(
        self, item: HackerNewsStory
    ) -> ArticleMetadata:
        return ArticleMetadata(
            url=urlparse(item.url),
            title=item.title,
            source=Source.HACKER_NEWS,
            publication_date_utc=item.time,
            score=item.score,
        )
