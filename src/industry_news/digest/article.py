from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional
from urllib.parse import ParseResult

from industry_news.sources import Source
from industry_news import markdown as md


@dataclass(frozen=True)
class ArticleMetadata:
    title: str
    source: Source
    url: ParseResult
    publication_date_utc: datetime
    score: int
    context: Dict[str, str] = field(default_factory=lambda: defaultdict(str))
    why_is_relevant: Optional[str] = None

    def description(self) -> str:
        context_str: str = " ".join(
            [f"{k.capitalize()}: {v}." for k, v in self.context.items()]
        )
        return f"Title: {self.title}. {context_str}"

    @staticmethod
    def title_from_description(description: str) -> str:
        return description.split("Title: ")[1].split(".")[0]


@dataclass(frozen=True)
class ArticleSummary:
    metadata: ArticleMetadata
    summary: str

    def to_markdown_str(self) -> str:
        title_link: str = md.link(
            f"[{self.metadata.score}] {self.metadata.title}",
            self.metadata.url.geturl(),
        )
        title_header: str = md.header(title_link, level=4)
        collapsible_summary: str = md.collapsible_section(
            self.summary, self.metadata.why_is_relevant or "Summary"
        )
        return f"{title_header}\n" f"{collapsible_summary}"


def summaries_to_markdown(summaries: List[ArticleSummary]) -> str:
    return "\n\n".join([summary.to_markdown_str() for summary in summaries])
