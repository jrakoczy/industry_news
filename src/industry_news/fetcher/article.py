from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Optional
from urllib.parse import ParseResult


@dataclass
class ArticleMetadata:
    title: str
    url: ParseResult
    publication_date: datetime
    score: int
    context: Dict[str, str] = field(default_factory=lambda: defaultdict(str))


@dataclass
class Article:
    metadata: ArticleMetadata
    content: Optional[str] = None
    summary: Optional[str] = None
