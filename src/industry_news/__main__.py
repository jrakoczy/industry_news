import logging
from datetime import datetime, timedelta, timezone
from typing import List
from industry_news.digest.article import ArticleMetadata, ArticleSummary
import argparse
from pathlib import Path

from industry_news.fetcher.futuretools_scraper import FutureToolsScraper
from industry_news.fetcher.hackernews_scraper import HackerNewsScraper
from industry_news.fetcher.reddit_api import RedditApi
from industry_news.fetcher.researchhub_api import ResearchHubApi
from industry_news.llm import ArticleFiltering, TextSummarizer


logging.basicConfig(level=logging.INFO)


def main() -> None:
    default_since = datetime.now() - timedelta(days=1)
    args = _parse_args(default_since)
    # NewsDigest().to_markdown_file(args.since, args.until, args.output_file)

    since: datetime = datetime.now() - timedelta(hours=2)
    results: List[ArticleSummary] = ResearchHubApi().article_summaries(
        since=since.astimezone(timezone.utc),
        until=datetime.now().astimezone(timezone.utc),
    )

    filtered = ArticleFiltering().filter_articles([result.metadata for result in results])

    summaries = TextSummarizer().summarize(
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


def _parse_datetime_in_utc(date_string: str) -> datetime:
    dt = datetime.fromisoformat(date_string)
    return dt.astimezone(timezone.utc)


def _parse_args(default_since: datetime) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--since",
        type=_parse_datetime_in_utc,
        default=default_since.isoformat(),
        help=(
            "Optional parameter in ISO-8601 format and local time zone."
            "Will only analyze articles newer than this date-time."
            "Defaults to 24 hours ago."
        ),
    )
    parser.add_argument(
        "--until",
        type=_parse_datetime_in_utc,
        default=datetime.now().isoformat(),
        help=(
            "Optional parameter in ISO-8601 format and local time zone."
            "Will only analyze articles older than this date-time."
            "Defaults to now."
        ),
    )
    parser.add_argument(
        "--output-file",
        type=Path,
        help=(
            "Optional parameter."
            "The output file the news digest will be written to (in Markdown)."
            "Defaults to 'news_digest_<since>_<until>.md'."
        ),
    )
    return parser.parse_args()


if __name__ == "__main__":
    main()
