from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, Optional
from urllib.parse import ParseResult


class SOURCE(Enum):
    REDDIT = "reddit"
    HACKER_NEWS = "hackernews"
    RESEARCH_HUB = "researchhub"
    FUTURE_TOOLS = "futuretools"


@dataclass
class ArticleMetadata:
    title: str
    source: SOURCE
    url: ParseResult
    publication_date: datetime
    score: int
    context: Dict[str, str] = field(default_factory=lambda: defaultdict(str))

    def description(self) -> str:
        context_str: str = " ".join(
            [f"{k.capitalize()}: {v}." for k, v in self.context.items()]
        )
        return f"Title: {self.title}. {context_str}"


@dataclass
class Article:
    metadata: ArticleMetadata
    content: Optional[str] = None
    summary: Optional[str] = None
