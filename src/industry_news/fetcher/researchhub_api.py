from datetime import datetime
from typing import List
from urllib.parse import ParseResult, urlparse
import requests
from industry_news.fetcher.fetcher import ArticleMetadata, Fetcher
from industry_news.fetcher.web_tools import construct_url

BASE_URL: str = (
    "https://backend.researchhub.com/api/"
)
SITE_LINK: ParseResult = construct_url(
    base_url=BASE_URL,
    relative_path="researchhub_unified_document/get_unified_documents/",
    params={"ordering": "new", "time": "all", "type": "all"}
)


class ResearchHubApi(Fetcher):

    def articles_metadata(
        self, since: datetime, until: datetime
    ) -> List[ArticleMetadata]:
        page: int = 1
        articles: List[ArticleMetadata] = []
        site_link: ParseResult = SITE_LINK
        while True:

            response: requests.Response = requests.get(site_link.geturl())
            data: dict = response.json()
            results: List[dict] = data.get("results", [])
            for result in results:
                publication_date: datetime = datetime.strptime(
                    result["created_date"], "%Y-%m-%dT%H:%M:%S.%fZ"
                )
                
                if publication_date < since:
                    break
                if publication_date > until:
                    continue
                
                url: ParseResult = urlparse(result["documents"]["file"])
                score: int = result["score"]
                # title: str = result["documents"]["title"]
                
                article: ArticleMetadata = ArticleMetadata(
                    url=url, publication_date=publication_date, score=score
                )
                articles.append(article)
            page += 1
            site_link = f"page={page}"
            
        return articles
