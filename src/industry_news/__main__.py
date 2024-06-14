import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
import argparse
from pathlib import Path

from industry_news.digest.news_digest import NewsDigest

from industry_news.utils import load_datetime_from_file, write_datetime_to_file

logging.basicConfig(level=logging.INFO)

LAST_DIGEST_END = Path("last_digest_end.txt")


def main() -> None:
    default_since: int = _default_since_days()
    args = _parse_args(default_since)
    now: datetime = datetime.now().astimezone(timezone.utc)
    NewsDigest().to_markdown_file(
        now - args.since_days,
        now - args.until_days,
        args.output_file
    )
    write_datetime_to_file(LAST_DIGEST_END, args.until)


def _default_since_days() -> int:
    last_digest_end: Optional[datetime] = load_datetime_from_file(
        LAST_DIGEST_END
    )
    return (
        (datetime.now() - last_digest_end).days + 1
        if last_digest_end
        else 9
    )


def _parse_args(default_since: int) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--since-days",
        type=lambda days: timedelta(days=days),
        default=timedelta(days=default_since),
        help=(
            "Optional parameter. Will only analyze articles newer "
            "than --since-days ago."
            "Defaults to 9 days ago."
        ),
    )
    parser.add_argument(
        "--until-days",
        type=lambda days: timedelta(days=days),
        default=timedelta(days=default_since + 7),
        help=(
            "Optional parameter. Will only analyze articles that are older "
            "than --until-days ago."
            "Defaults to --since-days + 7 days."
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
