import logging
from typing import List
from industry_news.article import Article
from datetime import datetime, timedelta
from industry_news.fetcher.hackernews_crawler import HackerNewsCrawler
from industry_news.fetcher.researchhub_api import ResearchHubApi
from industry_news.llm import _to_chunks
from industry_news.config import load_secrets

logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger(__name__)


def main():
    since: datetime = datetime.now() - timedelta(hours=2)
    results: List[Article] = HackerNewsCrawler().articles_metadata(since=since)

    chunks: List[str] = _to_chunks(
        articles_metadata=results, chunk_size=100
    )
    [print(f"{len(chunk)} | {chunk}") for chunk in chunks]


if __name__ == "__main__":
    main()
