import logging
from typing import List
from industry_news.fetcher.article import ArticleMetadata
from datetime import datetime, timedelta
from industry_news.fetcher.researchhub_api import ResearchHubApi

logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger(__name__)


def main():
    LOGGER.info("Fetching article titles...")
    since: datetime = datetime.now() - timedelta(hours=2)
    results: List[ArticleMetadata] = ResearchHubApi().articles_metadata(
        since=since
    )
    [print(metadata) for metadata in results]


if __name__ == "__main__":
    main()
