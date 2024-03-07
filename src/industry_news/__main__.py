import logging
from typing import List
from industry_news.fetcher.article import Article
from datetime import datetime, timedelta
from industry_news.fetcher.researchhub_api import ResearchHubApi

logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger(__name__)


def main():
    LOGGER.info("Fetching article titles...")
    since: datetime = datetime.now() - timedelta(hours=4)
    results: List[Article] = ResearchHubApi().articles(since=since)
    [print(metadata) for metadata in results]


if __name__ == "__main__":
    main()
