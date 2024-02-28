from datetime import datetime
from abc import ABC, abstractmethod
import urllib.parse
from typing import List


class ArticleMetadata:
    def __init__(
        self,
        url: urllib.parse.ParseResult,
        publication_date: datetime,
        score: int,
    ):
        self.url = url
        self.publication_date = publication_date
        self.score = score

    def __str__(self):
        return (
            f"ArticleMetadata(url={self.url.geturl()}, "
            f"publication_date={self.publication_date}, "
            f"score={self.score})"
        )


class Fetcher(ABC):
    @abstractmethod
    def article_urls(
        self, since: datetime, until: datetime = datetime.now()
    ) -> List[ArticleMetadata]:
        pass
