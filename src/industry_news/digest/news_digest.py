from datetime import datetime
from typing import List

from industry_news.config import SingleSourceConfig, load_config
from industry_news.digest.article import ArticleMetadata, ArticleSummary
from industry_news.fetcher.fetcher import (
    METADATA_FETCHERS_BY_SOURCE,
    SUMMARY_FETCHERS_BY_SOURCE,
    MetadataFetcher,
    SummaryFetcher,
    fetch_site_text,
)
from industry_news.llm import ArticleFiltering, TextSummarizer


class NewsDigest:

    @staticmethod
    def _init_summary_fetchers() -> List[SummaryFetcher]:
        with_summary_sources: List[SingleSourceConfig] = (
            load_config().sources.with_summary
        )
        return [
            SUMMARY_FETCHERS_BY_SOURCE[config.name]()
            for config in with_summary_sources
        ]

    @staticmethod
    def _init_metadata_fetchers() -> List[MetadataFetcher]:
        with_summary_sources: List[SingleSourceConfig] = (
            load_config().sources.without_summary
        )
        fetchers: List[MetadataFetcher] = []

        for config in with_summary_sources:
            if config.subspaces:
                for subspace in config.subspaces:
                    fetchers.append(
                        METADATA_FETCHERS_BY_SOURCE[config.name](subspace)
                    )
            else:
                fetchers.append(METADATA_FETCHERS_BY_SOURCE[config.name](""))

        return fetchers

    def __init__(
        self,
        text_summarizer: TextSummarizer = TextSummarizer(),
        article_filtering: ArticleFiltering = ArticleFiltering(),
        summary_fetchers: List[SummaryFetcher] = _init_summary_fetchers(),
        metadata_fetchers: List[MetadataFetcher] = _init_metadata_fetchers(),
    ):
        self._text_summarizer = text_summarizer
        self._article_filtering = article_filtering
        self._summary_fetchers = summary_fetchers
        self._metadata_fetchers = metadata_fetchers

    def to_markdown_file(
        self, since: datetime, until: datetime = datetime.now()
    ) -> None:
        for fetcher in self._metadata_fetchers:
            articles_metadata: List[ArticleMetadata] = (
                fetcher.articles_metadata(since, until)
            )
            filtered_metadata: List[ArticleMetadata] = (
                self._article_filtering.filter_articles(articles_metadata)
            )
            summary_texts: List[str] = self._fetch_summary_texts(
                filtered_metadata
            )
            summaries: List[ArticleSummary] = [
                ArticleSummary(metadata, summary)
                for metadata, summary in zip(filtered_metadata, summary_texts)
            ]

    def _fetch_summary_texts(
        self, filtered_metadata: List[ArticleMetadata]
    ) -> List[str]:
        summary_texts: List[str] = self._text_summarizer.summarize(
            (
                text
                for metadata in filtered_metadata
                if (text := fetch_site_text(metadata.url)) is not None
            )
        )
        return summary_texts