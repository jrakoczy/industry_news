from typing import List
from crawler.hackernews_crawler import articles


if __name__ == "__main__":
    results: List[str] = articles()
    print(results[0])
