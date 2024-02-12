from typing import List
from crawler.hackernews_crawler import articles
from datetime import datetime, timedelta


if __name__ == "__main__":
    since: datetime = datetime.now() - timedelta(hours=24)
    results: List[str] = articles(since)
    print(len(results))
