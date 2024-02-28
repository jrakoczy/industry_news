import logging
from typing import List
from industry_news.crawler.hackernews_crawler import articles
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger(__name__)


def main():
    LOGGER.info("Fetching article titles...")
    since: datetime = datetime.now() - timedelta(hours=2)
    results: List[str] = articles(since=since)
    print(len(results))


if __name__ == "__main__":
    main()
