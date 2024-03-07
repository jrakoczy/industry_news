import logging
from urllib.parse import ParseResult, urlparse
from datetime import datetime
from typing import List, cast
from redditwarp.SYNC import Client
from redditwarp.models.submission import LinkPost, Submission
from industry_news.fetcher.fetcher import Fetcher, ArticleMetadata
from industry_news.utils import retry

LOGGER = logging.getLogger(__name__)


class RedditApi(Fetcher):

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        subreddit: str,
    ):
        self._reddit: Client = Client(client_id, client_secret)
        self._subreddit: str = subreddit

    def articles_metadata(
        self, since: datetime, until: datetime = datetime.now()
    ) -> List[ArticleMetadata]:
        return retry(  # No convenient retry mechanism in redditwarp
            lambda: self.articles_metadata_wihtout_retries(since, until),
            delay_range_s=(5, 5),
        )

    def articles_metadata_wihtout_retries(
        self, since: datetime, until: datetime = datetime.now()
    ) -> List[ArticleMetadata]:
        LOGGER.info(
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

            if metadata.publication_date > until:
                continue
            elif metadata.publication_date < since:
                break

            articles.append(metadata)

        return articles

    @staticmethod
    def _single_article_metadata(submission: Submission) -> ArticleMetadata:
        publication_date: datetime = datetime.fromtimestamp(
            submission.created_ut
        )
        return ArticleMetadata(
            url=RedditApi._single_article_url(submission),
            title=submission.title,
            publication_date=publication_date,
            score=submission.score,  # Upvotes - downvotes
            context={"subreddit": submission.subreddit.name},
        )

    @staticmethod
    def _single_article_url(submission: Submission) -> ParseResult:
        url: str = (
            cast(LinkPost, submission).link
            if isinstance(submission, LinkPost)
            else submission.permalink
        )
        return urlparse(url)
