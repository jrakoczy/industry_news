from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from industry_news.config import load_config
from industry_news.digest.article import (
    ArticleMetadata,
    ArticleSummary,
    summaries_to_markdown,
)
from industry_news.fetcher.fetcher import (
    Fetcher,
    MetadataFetcher,
    SummaryFetcher,
    fetch_site_text,
)
from industry_news.fetcher.fetchers_init import (
    init_metadata_fetchers,
    init_summary_fetchers,
)
from industry_news.llm import ArticleFiltering, TextSummarizer
from industry_news.markdown import header
from industry_news.utils import fail_gracefully


@dataclass(frozen=True, eq=False, match_args=False)
class NewsDigest:

    _text_summarizer: TextSummarizer = TextSummarizer()
    _article_filtering: ArticleFiltering = ArticleFiltering()
    _summary_fetchers: List[SummaryFetcher] = field(
        default_factory=lambda: init_summary_fetchers(load_config().sources)
    )
    _metadata_fetchers: List[MetadataFetcher] = field(
        default_factory=lambda: init_metadata_fetchers(load_config().sources)
    )

    def to_markdown_file(
        self,
        since: datetime,
        until: Optional[datetime] = None,
        output_file: Optional[Path] = None,
        articles_per_source_limit: int = (
            load_config().sources.articles_per_source_limit
        ),
    ) -> None:
        """Fetches articles from sources defined in _summary_fetchers and
        _metadata_fetchers. Filters out articles that do not meet the criteria,
        summarizes those that remained (if necessary) and writes results to a
        markdown file.

        Args:
            articles_per_source_limit (int, optional): The number of articles
            that will be writeen to a markdown file for a given source +
            subspace(subreddit, category, etc). The actual number of fetched
            and summarized articles will be larger.

            Defaults to `articles_per_source_limit` config value.
        """
        if not until:
            until = datetime.now()

        if not output_file:
            output_file = NewsDigest._output_file(since, until)

        self._from_sources_without_summaries(
            since, until, output_file, articles_per_source_limit
        )

        self._from_sources_providing_summaries(
            since, until, output_file, articles_per_source_limit
        )

    def _from_sources_providing_summaries(
        self,
        since: datetime,
        until: datetime,
        output_file: Path,
        articles_per_source_limit: int,
    ) -> None:
        for summary_fetcher in self._summary_fetchers:
            summaries: List[ArticleSummary] = (
                summary_fetcher.article_summaries(since, until)
            )

            filtered_summaries: List[ArticleSummary] = (
                self._article_filtering.filter_summaries(summaries)
            )
            filtered_summaries = filtered_summaries[:articles_per_source_limit]

            # Make sure we write to a file after processing each source, so we
            # can preserve some results even in case of a failure.
            if filtered_summaries:
                NewsDigest._write_markdown_to_file(
                    summary_fetcher, output_file, filtered_summaries
                )

    def _from_sources_without_summaries(
        self,
        since: datetime,
        until: datetime,
        output_file: Path,
        articles_per_source_limit: int,
    ) -> None:
        for metadata_fetcher in self._metadata_fetchers:
            summaries: Optional[List[ArticleSummary]] = fail_gracefully(
                lambda: self._fetch_and_summarize(
                    metadata_fetcher, since, until, articles_per_source_limit
                )
            )

            # Make sure we write to a file after processing each source, so we
            # can preserve some results even in case of a failure.
            if summaries:
                NewsDigest._write_markdown_to_file(
                    metadata_fetcher, output_file, summaries
                )

    @staticmethod
    def _write_markdown_to_file(
        fetcher: Fetcher, output_file: Path, summaries: List[ArticleSummary]
    ) -> None:
        subspace: str = f": {fetcher.subspace()}" if fetcher.subspace() else ""
        section_header: str = header(
            f"{fetcher.source().value}{subspace}", level=2
        )
        articles_markdown_str: str = summaries_to_markdown(summaries)

        with output_file.open("a") as file:
            file.write(f"{section_header}\n{articles_markdown_str}\n\n")

    def _fetch_and_summarize(
        self,
        fetcher: MetadataFetcher,
        since: datetime,
        until: datetime,
        articles_per_source_limit: int,
    ) -> List[ArticleSummary]:
        articles_metadata: List[ArticleMetadata] = fetcher.articles_metadata(
            since, until
        )
        filtered_metadata: List[ArticleMetadata] = (
            self._article_filtering.filter_metadata(articles_metadata)
        )
        filtered_metadata = filtered_metadata[:articles_per_source_limit]
        summary_texts: List[str] = self._summarize_articles(filtered_metadata)
        return [
            ArticleSummary(metadata, summary)
            for metadata, summary in zip(filtered_metadata, summary_texts)
        ]

    def _summarize_articles(
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

    @staticmethod
    def _output_file(since: datetime, until: datetime) -> Path:
        datetime_format: str = "%Y-%m-%d-%H"
        return Path(
            f"news_digest"
            f"_{since.strftime(datetime_format)}"
            f"_{until.strftime(datetime_format)}.md"
        )
