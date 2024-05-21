import logging
from urllib.parse import ParseResult, urlparse
from datetime import datetime
from typing import List, Optional
from redditwarp.SYNC import Client
from redditwarp.models.submission import LinkPost, Submission
from industry_news.digest.article import ArticleMetadata
from industry_news.config import Secrets, load_secrets
from industry_news.sources import Source
from industry_news.fetcher.fetcher import MetadataFetcher
from industry_news.utils import retry, to_utc_datetime


class RedditApi(MetadataFetcher):

    _LOGGER = logging.getLogger(__name__)

    @staticmethod
    def _reddit_client() -> Client:
        secrets: Secrets = load_secrets()
        return Client(
            secrets.reddit.client_id,
            secrets.reddit.client_secret.get_secret_value(),
        )

    @staticmethod
    def source() -> Source:
        return Source.REDDIT

    def subspace(self) -> Optional[str]:
        return self._subreddit

    def __init__(self, subreddit: str, reddit: Client = _reddit_client()):
        if not subreddit:
            raise ValueError("Subreddit cannot be blank.")
        self._reddit = reddit
        self._subreddit = subreddit

    def articles_metadata(
        self, since: datetime, until: datetime
    ) -> List[ArticleMetadata]:
        return retry(  # No convenient retry mechanism in redditwarp
            lambda: self.articles_metadata_wihtout_retries(since, until),
            delay_range_s=(5, 5),
        )

    def articles_metadata_wihtout_retries(
        self, since: datetime, until: datetime = datetime.now()
    ) -> List[ArticleMetadata]:
        self._LOGGER.info(
            "Fetching articles from %s between %s and %s",
            self._subreddit,
            since,
            until,
        )
        iterator = self._reddit.p.subreddit.pull.new(sr=self._subreddit)
        articles: List[ArticleMetadata] = []

        for submission in iterator:
            metadata: ArticleMetadata = RedditApi._single_article_metadata(
                submission
            )

            if metadata.publication_date_utc > until:
                continue
            elif metadata.publication_date_utc < since:
                break

            articles.append(metadata)

        return articles

    @staticmethod
    def _single_article_metadata(submission: Submission) -> ArticleMetadata:
        publication_date: datetime = to_utc_datetime(submission.created_ut)
        return ArticleMetadata(
            url=RedditApi._single_article_url(submission),
            title=submission.title,
            source=Source.REDDIT,
            publication_date_utc=publication_date,
            score=submission.score,  # Upvotes - downvotes
            context={"subreddit": submission.subreddit.name},
        )

    @staticmethod
    def _single_article_url(submission: Submission) -> ParseResult:
        url: str = (
            submission.link
            if isinstance(submission, LinkPost)
            else submission.permalink
        )
        return urlparse(url)
