from decimal import Decimal
import math
import os
from typing import Any, Callable, Dict, List, Set, Type, TypeVar
from attr import dataclass
from langchain.prompts import PromptTemplate
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_community.callbacks import openai_info
from langchain_openai import OpenAI
from langchain_text_splitters import RecursiveCharacterTextSplitter
from industry_news.article import SOURCE, ArticleMetadata
from industry_news.fetcher.web_tools import DELAY_RANGE_S
from industry_news.utils import (
    load_as_string,
    load_config,
    load_resource,
    load_secrets,
    retry,
)


T = TypeVar("T")


@dataclass
class Model:
    name: str
    max_prompt_length: int
    token_cost_usd: Decimal
    max_cost_usd: Decimal
    out_in_cost_ratio: Decimal


class FilterArticlesResponse(BaseModel):
    reasonsings: List[str] = Field(
        description="Reasonings why an article was selected or not",
    )
    relevant_articles: List[str] = Field(
        description="Titles of relevant articles",
    )


class ArticleFiltering:
    _FILTER_PROMPT_MAPPINGS = {
        SOURCE.REDDIT: {"source_prompt": "Reddit posts"},
        SOURCE.HACKER_NEWS: {"source_prompt": "Hacker News posts"},
        SOURCE.RESEARCH_HUB: {"source_prompt": "Research Hub posts"},
        SOURCE.FUTURE_TOOLS: {
            "source_prompt": "articles from Future Tools, a site aggregating AI news"
        },
    }
    _config = load_config()
    _openai_factory: Callable[[str], OpenAI] = (
        lambda filter_model_name: OpenAI(
            model_name=filter_model_name,
            openai_api_key=load_secrets()["llm"]["openai_api_key"],
            max_tokens=-1,  # -1 == context_size - prompt length
        )
    )

    def __init__(
        self,
        filter_model_name: str = _config["llm"]["filter_model"]["name"],
        max_query_cost_usd: Decimal = _config["llm"]["filter_model"][
            "max_query_cost_usd"
        ],
        filter_prompt_file_name: str = "prompt.txt",
        openai_factory: Callable[[str], OpenAI] = _openai_factory,
        prompt_to_completion_len_ratio: float = _config["llm"]["filter_model"][
            "prompt_to_completion_len_ratio"
        ],
    ) -> None:
        self._filter_prompt_file_name = filter_prompt_file_name
        self._openai = openai_factory(filter_model_name)
        self._openai.with_structured_output(
            FilterArticlesResponse, method="json_mode"
        )
        self._max_query_cost_usd = max_query_cost_usd
        self._cost_calculator = OpenAICostCalculator(
            openai=self._openai,
            filter_prompt_file_name=filter_prompt_file_name,
            prompt_to_completion_len_ratio=prompt_to_completion_len_ratio,
        )

    def filter_articles(
        self, articles_metadata: List[ArticleMetadata]
    ) -> List[ArticleMetadata]:
        """
        Filters the list of articles based on criteria defined in prompt files.

        Returns:
            List[ArticleMetadata]: A returned list is sorted in descending
            order by score.
        """
        if not articles_metadata:
            return []

        source: SOURCE = articles_metadata[0].source
        sorted_articles_metadata: List[ArticleMetadata] = self._sort_by_score(
            articles_metadata
        )
        article_titles_chunks: List[str] = self._to_titles_chunks(
            sorted_articles_metadata, source
        )
        remaining_titles: Set[str] = self._filter_titles(
            source, article_titles_chunks
        )

        return [
            metadata
            for metadata in sorted_articles_metadata
            if metadata.title in remaining_titles
        ]

    def _sort_by_score(
        self, articles_metadata: List[ArticleMetadata]
    ) -> List[ArticleMetadata]:
        return sorted(
            articles_metadata,
            key=lambda metadata: metadata.score,
            reverse=True,
        )

    def _to_titles_chunks(
        self, article_metadata: List[ArticleMetadata], source: SOURCE
    ) -> List[str]:
        chunks: List[str] = _to_chunks(
            text=ArticleFiltering._to_text(article_metadata),
            chunk_size=self._titles_chunk_max_token_count(source),
            model_name=self._openai.model_name,
        )
        max_chunks: int = self._cost_calculator.max_chunks_within_budget(
            self._max_query_cost_usd
        )
        cost_limited_chunks: List[str] = chunks[:max_chunks]
        return [
            ArticleFiltering._number_lines(chunk)
            for chunk in cost_limited_chunks
        ]

    def _filter_titles(
        self, source: SOURCE, numbered_chunks: List[str]
    ) -> Set[str]:
        remaining_titles: Set[str] = set()

        for articles_chunk in numbered_chunks:
            response: FilterArticlesResponse = self._invoke_model(
                source, articles_chunk
            )
            remaining_titles.update(response.relevant_articles)

        return remaining_titles

    def _invoke_model(
        self, source: SOURCE, articles_chunk: str
    ) -> FilterArticlesResponse:
        prompt: PromptTemplate = self._to_full_prompt(source)
        output: Any = retry(
            lambda: (prompt | self._openai).invoke(
                {"articles": articles_chunk}
            ),
            delay_range_s=DELAY_RANGE_S,
        )
        return _verify_output(output=output, type_=FilterArticlesResponse)

    def _to_full_prompt(self, source: SOURCE) -> PromptTemplate:
        prompt_template: PromptTemplate = _prompt_template(
            self._filter_prompt_file_name
        )
        # Encapsulate formatted prompt (str) in PromptTemplate again to be able
        # to use LCEL chains.
        return PromptTemplate.from_template(
            prompt_template.format(
                examples=ArticleFiltering._load_n_shot_text(source),
                *self._FILTER_PROMPT_MAPPINGS[source],
            )
        )

    def _titles_chunk_max_token_count(self, source: SOURCE) -> int:
        return int(
            (
                self._cost_calculator.max_prompt_length()
                - self._cost_calculator.prompt_template_token_count(
                    self._filter_prompt_file_name,
                    {"examples": ArticleFiltering._load_n_shot_text(source)},
                )
            )
            * 0.95,  # Lazy solution to avoid exceeding a context size after
            # prepending a number a the beginning of each article title line.
        )

    @staticmethod
    def _to_text(articles_metadata: List[ArticleMetadata]) -> str:
        return f"{os.linesep}".join(
            [metadata.description() for metadata in articles_metadata]
        )

    @staticmethod
    def _number_lines(text: str) -> str:
        return os.linesep.join(
            [f"{i+1}. {line}" for i, line in enumerate(text.split(os.linesep))]
        )

    @staticmethod
    def _load_n_shot_text(source: SOURCE) -> str:
        return load_as_string(f"n_shot/{source}_n_shot.txt")


class OpenAICostCalculator:
    def __init__(
        self,
        openai: OpenAI,
        filter_prompt_file_name: str,
        prompt_to_completion_len_ratio: float,
    ) -> None:
        self._openai = openai
        self._filter_prompt_file_name = filter_prompt_file_name
        self._prompt_to_completion_len_ratio = prompt_to_completion_len_ratio

    def max_chunks_within_budget(self, max_query_cost_usd: Decimal) -> int:
        return math.floor(
            max_query_cost_usd
            / (self.max_prompt_cost_usd() + self.max_completion_cost_usd())
        )

    def max_prompt_cost_usd(self) -> Decimal:
        return Decimal(
            self.max_prompt_length()
            * openai_info.get_openai_token_cost_for_model(
                model_name=self._openai.model_name,
                num_tokens=1,
                is_completion=False,
            )
        )

    def max_completion_cost_usd(self) -> Decimal:
        max_completion_len: int = (
            self._openai.max_context_size - self.max_prompt_length()
        )
        return Decimal(
            max_completion_len
            * openai_info.get_openai_token_cost_for_model(
                model_name=self._openai.model_name,
                num_tokens=1,
                is_completion=True,
            )
        )

    def prompt_template_token_count(
        self, prompt_file_name: str, variables: Dict[str, str]
    ) -> int:
        prompt_template: PromptTemplate = _prompt_template(prompt_file_name)
        return self._openai.get_num_tokens(prompt_template.format(**variables))

    def max_prompt_length(self) -> int:
        return math.floor(
            self._openai.max_context_size
            * self._prompt_to_completion_len_ratio
        )


def _verify_output(output: Any, type_: Type[T]) -> T:
    if not isinstance(output, type_):
        raise ValueError(f"Expected output {type_}, got {type(output)}.")
    return output


def _to_chunks(text: str, chunk_size: int, model_name: str) -> List[str]:
    splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
        model_name=model_name,
        chunk_size=chunk_size,
        separators=[os.linesep],
        chunk_overlap=0,
    )
    return splitter.split_text(text)


def _prompt_template(prompt_file_name: str) -> PromptTemplate:
    return PromptTemplate.from_file(load_resource(prompt_file_name))
