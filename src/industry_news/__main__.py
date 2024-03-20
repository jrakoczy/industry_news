import logging
from re import S
from typing import List
from industry_news.article import Source, Article, ArticleMetadata
from datetime import datetime, timedelta
from industry_news.fetcher.hackernews_crawler import HackerNewsCrawler
from industry_news.llm import ArticleFiltering

logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger(__name__)


def main() -> None:
    since: datetime = datetime.now() - timedelta(hours=2)
    results: List[ArticleMetadata] = HackerNewsCrawler().articles_metadata(
        since=since
    )
    filtered = ArticleFiltering().filter_articles(results)
    print("end")


if __name__ == "__main__":
    main()
