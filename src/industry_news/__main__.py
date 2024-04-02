import logging
from datetime import datetime, timedelta
from industry_news.digest.news_digest import NewsDigest
import argparse
from pathlib import Path
from datetime import datetime, timedelta


logging.basicConfig(level=logging.INFO)


def _parse_args(default_since: datetime) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--since",
        type=datetime.fromisoformat,
        default=default_since.isoformat(),
        help=(
            "ISO-8601 format."
            "Will only analyze articles newer than this date."
            "Defaults to 24 hours ago."
        ),
    )
    parser.add_argument(
        "--until",
        type=datetime.fromisoformat,
        help=(
            "ISO-8601 format."
            "Will only analyze articles older than this date."
            "Defaults to now."
        ),
    )
    parser.add_argument(
        "--output-file",
        type=Path,
        help=(
            "The output file the news digest will be written to (in Markdown)."
        ),
    )
    return parser.parse_args()


def main() -> None:
    default_since = datetime.now() - timedelta(days=1)
    args = _parse_args(default_since)
    NewsDigest().to_markdown_file(args.since, args.until, args.output_file)

    # since: datetime = datetime.now() - timedelta(hours=2)
    # results: List[ArticleMetadata] = HackerNewsCrawler().articles_metadata(
    #     since=since
    # )
    # filtered = ArticleFiltering().filter_articles(results)

    # summaries = TextSummarizer().summarize(
    #     (
    #         "This is a very long test article."
    #         "With basically no meaningful content."
    #         "With basically no meaningful content."
    #         "With basically no meaningful content."
    #         "With basically no meaningful content."
    #         "With basically no meaningful content."
    #         for _ in range(1)
    #     )
    # )


if __name__ == "__main__":
    main()
