import logging
from typing import List
from industry_news.fetcher.fetcher import ArticleMetadata
from industry_news.fetcher.hackernews_crawler import HackerNewsCrawler
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger(__name__)


def main():
    LOGGER.info("Fetching article titles...")
    since: datetime = datetime.now() - timedelta(hours=2)
    results: List[ArticleMetadata] = HackerNewsCrawler().article_urls(
        since=since
    )
    [print(metadata) for metadata in results]


if __name__ == "__main__":
    main()
