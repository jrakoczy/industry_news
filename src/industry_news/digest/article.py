from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Optional
from urllib.parse import ParseResult

from industry_news.fetcher.fetcher import Source


@dataclass(frozen=True)
class ArticleMetadata:
    title: str
    source: Source
    url: ParseResult
    publication_date: datetime
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
