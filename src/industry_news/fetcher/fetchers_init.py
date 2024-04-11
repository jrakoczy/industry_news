from industry_news.config import SingleSourceConfig, SourcesConfig
from industry_news.sources import Source
from industry_news.fetcher.fetcher import MetadataFetcher, SummaryFetcher
from industry_news.fetcher.futuretools_scraper import FutureToolsScraper
from industry_news.fetcher.hackernews_scraper import HackerNewsScraper


from typing import Callable, Dict, List, Optional

from industry_news.fetcher.reddit_api import RedditApi
from industry_news.fetcher.researchhub_api import ResearchHubApi


METADATA_FETCHERS_BY_SOURCE: Dict[
    Source, Callable[[Optional[str]], MetadataFetcher]
] = {
    Source.REDDIT: lambda subspace: _reddit_api(subspace),
    Source.HACKER_NEWS: lambda _: HackerNewsScraper(),
    Source.FUTURE_TOOLS: lambda _: FutureToolsScraper(),
}
SUMMARY_FETCHERS_BY_SOURCE: Dict[Source, Callable[[], SummaryFetcher]] = {
    Source.RESEARCH_HUB: lambda: ResearchHubApi()
}


def init_summary_fetchers(
    sources_config: SourcesConfig,
) -> List[SummaryFetcher]:
    with_summary_sources: List[SingleSourceConfig] = (
        sources_config.with_summary
    )
    return [
        SUMMARY_FETCHERS_BY_SOURCE[config.name]()
        for config in with_summary_sources
    ]


def init_metadata_fetchers(
    sources_config: SourcesConfig,
) -> List[MetadataFetcher]:
    without_summary_sources: List[SingleSourceConfig] = (
        sources_config.without_summary
    )
    fetchers: List[MetadataFetcher] = []

    for config in without_summary_sources:
        if config.subspaces:
            for subspace in config.subspaces:
                fetchers.append(
                    METADATA_FETCHERS_BY_SOURCE[config.name](subspace)
                )
        else:
            fetchers.append(METADATA_FETCHERS_BY_SOURCE[config.name](None))

    return fetchers


def _reddit_api(subreddit: Optional[str]) -> RedditApi:
    if subreddit:
        return RedditApi(subreddit)
    else:
        raise ValueError("Subreddit name not provided.")
