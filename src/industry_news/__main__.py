import logging
from typing import Dict, List, Any
from industry_news.fetcher.fetcher import ArticleMetadata
from datetime import datetime, timedelta

from industry_news.fetcher.reddit_api_fetcher import RedditApiFetcher
from industry_news.utils import load_secrets

logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger(__name__)


def main():
    LOGGER.info("Fetching article titles...")
    since: datetime = datetime.now() - timedelta(hours=2)
    secrets: Dict[str, Any] = load_secrets()["reddit"]
    results: List[ArticleMetadata] = RedditApiFetcher(
        client_id=secrets["client_id"],
        client_secret=secrets["client_secret"],
        subreddit="Games",
    ).articles_metadata(since=since)
    [print(metadata) for metadata in results]


if __name__ == "__main__":
    main()
