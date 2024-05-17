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
    default_since = _get_default_since()
    args = _parse_args(default_since)
    NewsDigest().to_markdown_file(args.since, args.until, args.output_file)
    write_datetime_to_file(LAST_DIGEST_END, args.until)


def _get_default_since() -> datetime:
    last_digest_end: Optional[datetime] = load_datetime_from_file(
        LAST_DIGEST_END
    )
    default_since: datetime = (
        last_digest_end
        if last_digest_end
        else datetime.now() - timedelta(days=2)
    )
    return default_since


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
            "Defaults to 2 days ago, give users some time to upvote content."
        ),
    )
    parser.add_argument(
        "--until",
        type=_parse_datetime_in_utc,
        default=(default_since + timedelta(days=1)).isoformat(),
        help=(
            "Optional parameter in ISO-8601 format and local time zone."
            "Will only analyze articles older than this date-time."
            "Defaults to since + 1 day"
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
