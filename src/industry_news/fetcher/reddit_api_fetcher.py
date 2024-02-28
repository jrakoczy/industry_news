from urllib.parse import ParseResult, urlparse
from datetime import datetime
from typing import List, cast
from redditwarp.SYNC import Client
from redditwarp.models.submission import LinkPost, Submission
from industry_news.fetcher.fetcher import Fetcher, ArticleMetadata


class RedditApiFetcher(Fetcher):

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
        iterator = self._reddit.p.subreddit.pull.new(sr=self._subreddit)
        articles: List[ArticleMetadata] = []

        for submission in iterator:
            publication_date: datetime = datetime.fromtimestamp(
                submission.created_ut
            )

            if publication_date > until:
                continue
            elif publication_date < since:
                break

            article_metadata: ArticleMetadata = ArticleMetadata(
                url=RedditApiFetcher._single_article_url(submission),
                publication_date=publication_date,
                score=submission.score,  # Upvotes - downvotes
            )
            articles.append(article_metadata)

        return articles

    @staticmethod
    def _single_article_url(submission: Submission) -> ParseResult:
        url: str = (
            cast(LinkPost, submission).link
            if isinstance(submission, LinkPost)
            else submission.permalink
        )
        return urlparse(url)
