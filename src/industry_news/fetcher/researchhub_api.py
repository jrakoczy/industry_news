from datetime import datetime
from typing import Any, List
from urllib.parse import ParseResult, urlparse
from numpy import sinc
import requests
from industry_news.fetcher.fetcher import (
    ArticleMetadata,
    Fetcher,
    CONTINUE_PAGINATING,
)
from industry_news.fetcher.web_tools import (
    construct_url,
    get_with_retries,
    modify_url_query,
)

BASE_URL: str = "https://backend.researchhub.com/api/"
SITE_LINK: ParseResult = construct_url(
    base_url=BASE_URL,
    relative_path="researchhub_unified_document/get_unified_documents/",
    query_params={"ordering": "new", "time": "all", "type": "all"},
)


class ResearchHubApi(Fetcher):

    def articles_metadata(
        self, since: datetime, until: datetime
    ) -> List[ArticleMetadata]:

        page: int = 1
        articles: List[ArticleMetadata] = []
        site_link: ParseResult = SITE_LINK
        paginating: CONTINUE_PAGINATING = CONTINUE_PAGINATING.CONTINUE
        response: requests.Response = requests.get(site_link.geturl())

        while paginating == CONTINUE_PAGINATING.CONTINUE:

            data: Any = response.json()
            posts: List[Any] = data.get("results", [])

            paginating = ResearchHubApi._process_results_page(
                since, until, articles, posts
            )

            page += 1
            site_link = modify_url_query(site_link, {"page": str(page)})
            response = get_with_retries(site_link)
            if response.status_code == 404:
                paginating = CONTINUE_PAGINATING.STOP

        return articles

    @staticmethod
    def _process_results_page(
        since: datetime,
        until: datetime,
        articles: List[ArticleMetadata],
        posts: List[Any],
    ) -> CONTINUE_PAGINATING:
        for post in posts:
            metadata: ArticleMetadata = (
                ResearchHubApi._single_article_metadata(post)
            )
            paginating: CONTINUE_PAGINATING = CONTINUE_PAGINATING.CONTINUE

            if metadata.publication_date < since:
                paginating = CONTINUE_PAGINATING.STOP
                break
            if until >= metadata.publication_date >= since:
                articles.append(metadata)

        return paginating

    @staticmethod
    def _single_article_metadata(post: Any) -> ArticleMetadata:
        publication_date: datetime = datetime.strptime(
            post["created_date"], "%Y-%m-%dT%H:%M:%S.%fZ"
        )
        return ArticleMetadata(
            title=post["documents"]["title"],
            url=urlparse(post["documents"]["file"]),
            publication_date=publication_date,
            score=post["score"],
        )
