import logging
from typing import List
from industry_news.article import ArticleMetadata
from datetime import datetime, timedelta
from industry_news.config import load_secrets
from industry_news.fetcher.hackernews_crawler import HackerNewsCrawler
from industry_news.llm import ArticleFiltering, TextSummarization


logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger(__name__)


def main() -> None:
    # since: datetime = datetime.now() - timedelta(hours=2)
    # results: List[ArticleMetadata] = HackerNewsCrawler().articles_metadata(
    #     since=since
    # )
    # filtered = ArticleFiltering().filter_articles(results)

    summaries = TextSummarization().summarize(
        (
            "This is a very long test article."
            "With basically no meaningful content."
            "With basically no meaningful content."
            "With basically no meaningful content."
            "With basically no meaningful content."
            "With basically no meaningful content."
            for _ in range(1)
        )
    )
    print("end")


if __name__ == "__main__":
    main()
