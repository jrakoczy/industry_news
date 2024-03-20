from decimal import Decimal
from functools import lru_cache
import logging
import math
import os
from typing import Any, Callable, Dict, List, Optional, Set, Type, TypeVar
from langchain.prompts import PromptTemplate
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_community.callbacks import openai_info
from langchain_openai import ChatOpenAI
from langchain_openai.llms.base import BaseOpenAI
from langchain_text_splitters import RecursiveCharacterTextSplitter
from industry_news.article import Source, ArticleMetadata
from industry_news.config import FilterModelConfig, load_config, load_secrets
from industry_news.fetcher.web_tools import DELAY_RANGE_S
from industry_news.utils import (
    load_as_string,
    load_resource,
    retry,
)

_LOGGER = logging.getLogger(__name__)
T = TypeVar("T")


class FilterArticlesResponse(BaseModel):
    reasonings: List[str] = Field(
        description="Reasonings why an article was selected or not",
    )
    relevant_articles: List[int] = Field(
        description="Line numbers of relevant articles",
    )


class ArticleFiltering:
    _SOURCE_PROMPT_KEY = "source_prompt"
    _FILTER_PROMPT_MAPPINGS: Dict[Source, Dict[str, str]] = {
        Source.REDDIT: {_SOURCE_PROMPT_KEY: "Reddit posts"},
        Source.HACKER_NEWS: {_SOURCE_PROMPT_KEY: "Hacker News posts"},
        Source.RESEARCH_HUB: {_SOURCE_PROMPT_KEY: "Research Hub posts"},
        Source.FUTURE_TOOLS: {
            _SOURCE_PROMPT_KEY: "articles from Future Tools, "
            + "a site aggregating AI news"
        },
    }

    # We need to use ChatOpenAI instead of OpenAI to have structured output.
    _openai_factory: Callable[[str], ChatOpenAI] = (
        lambda model_name: ChatOpenAI(
            model_name=model_name,
            openai_api_key=load_secrets().llm.openai_api_key,
        )
    )

    def __init__(
        self,
        config: FilterModelConfig = load_config().llm.filter_model,
        filter_prompt_file_name: str = "prompt.txt",
        openai_factory: Callable[[str], ChatOpenAI] = _openai_factory,
    ) -> None:
        openai_model: ChatOpenAI = openai_factory(config.name)

        self._filter_prompt_file_name = filter_prompt_file_name
        self._model_name = openai_model.model_name
        self._model = openai_model.with_structured_output(
            FilterArticlesResponse, method="json_mode"
        )
        self._query_cost_limit_usd = config.query_cost_limit_usd
        self._cost_calculator = OpenAICostCalculator(
            openai=openai_model,
            filter_prompt_file_name=filter_prompt_file_name,
            prompt_to_completion_len_ratio=(
                config.prompt_to_completion_len_ratio
            ),
            context_size_limit=config.context_size_limit,
        )

    def filter_articles(
        self, articles_metadata: List[ArticleMetadata]
    ) -> List[ArticleMetadata]:
        """
        Filters the list of articles based on criteria defined in a prompt.

        Returns:
            List[ArticleMetadata]: A returned list is sorted in descending
            order by score.
        """
        if not articles_metadata:
            return []

        source: Source = articles_metadata[0].source
        _LOGGER.info(
            "Filtering %s articles. Estimated maximum query cost: %.3f USD.",
            source.value,
            float(self._cost_calculator.max_query_cost_usd()),
        )

        sorted_articles_metadata: List[ArticleMetadata] = self._sort_by_score(
            articles_metadata
        )
        article_titles_chunks: List[str] = self._titles_to_chunks(
            sorted_articles_metadata, source
        )
        remaining_titles: Set[str] = self._filter_titles_by_prompt(
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

    def _titles_to_chunks(
        self, article_metadata: List[ArticleMetadata], source: Source
    ) -> List[str]:
        chunks: List[str] = _to_chunks(
            text=ArticleFiltering._to_text(article_metadata),
            chunk_size=self._titles_chunk_max_token_count(source),
            model_name=self._model_name,
        )
        max_chunks: int = self._cost_calculator.max_chunks_within_budget(
            self._query_cost_limit_usd
        )
        cost_limited_chunks: List[str] = chunks[:max_chunks]
        return [
            ArticleFiltering._number_lines(chunk)
            for chunk in cost_limited_chunks
        ]

    def _filter_titles_by_prompt(
        self, source: Source, numbered_chunks: List[str]
    ) -> Set[str]:
        remaining_titles: Set[str] = set()

        for articles_chunk in numbered_chunks:
            response: FilterArticlesResponse = self._invoke_model(
                source, articles_chunk
            )
            remaining_titles.update(
                self._filter_titles_chunk(
                    articles_chunk, response.relevant_articles
                )
            )

        return remaining_titles

    def _invoke_model(
        self, source: Source, articles_chunk: str
    ) -> FilterArticlesResponse:
        prompt: PromptTemplate = _prompt_template(
            self._filter_prompt_file_name
        )
        prompt_variables: Dict[str, str] = ArticleFiltering._prompt_variables(
            source, articles_chunk
        )
        output: Any = retry(
            lambda: (prompt | self._model).invoke(prompt_variables),
            delay_range_s=DELAY_RANGE_S,
        )
        return _verify_output(output=output, type_=FilterArticlesResponse)

    @staticmethod
    def _filter_titles_chunk(
        articles_titles_chunk: str, line_numbers: List[int]
    ) -> List[str]:
        return [
            ArticleMetadata.title_from_description(line)
            for i, line in enumerate(articles_titles_chunk.split(os.linesep))
            if i + 1 in line_numbers
        ]

    def _titles_chunk_max_token_count(self, source: Source) -> int:
        prompt_variables: Dict[str, str] = ArticleFiltering._prompt_variables(
            source, ""
        )
        template_token_count: int = (
            self._cost_calculator.prompt_template_token_count(
                self._filter_prompt_file_name, prompt_variables
            )
        )
        max_chunk_token_count: int = (
            self._cost_calculator.max_prompt_token_count()
            - template_token_count
        )

        if max_chunk_token_count <= 0:
            raise ValueError(
                "The prompt is too long to fit a single article title chunk. "
                "Increase the context size "
                f"(currently: {self._cost_calculator.context_size}) "
                "or decrease the template length "
                f"(currently: {template_token_count})."
            )

        return int(
            max_chunk_token_count
            * 0.95,  # Lazy solution to avoid exceeding a context size after
            # prepending a number a the beginning of each article title line.
        )

    @classmethod
    def _prompt_variables(
        cls, source: Source, article_titles_chunks: str
    ) -> Dict[str, str]:
        return {
            **{
                "examples": ArticleFiltering._load_n_shot_text(source),
                "articles_list": article_titles_chunks,
            },
            **cls._FILTER_PROMPT_MAPPINGS[source],
        }

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
    def _load_n_shot_text(source: Source) -> str:
        return load_as_string(f"n_shot/{source.value}_n_shot.txt")


class OpenAICostCalculator:
    def __init__(
        self,
        openai: ChatOpenAI,
        filter_prompt_file_name: str,
        prompt_to_completion_len_ratio: float,
        context_size_limit: Optional[int] = None,
    ) -> None:
        self._openai = openai
        self._prompt_to_completion_len_ratio = prompt_to_completion_len_ratio
        self._context_size_limit = context_size_limit

    def max_chunks_within_budget(self, max_query_cost_usd: Decimal) -> int:
        return math.floor(
            max_query_cost_usd
            / (self.max_prompt_cost_usd() + self.max_completion_cost_usd())
        )

    @lru_cache
    def max_prompt_cost_usd(self) -> Decimal:
        return Decimal(
            self.max_prompt_token_count()
            * openai_info.get_openai_token_cost_for_model(
                model_name=self._openai.model_name,
                num_tokens=1,
                is_completion=False,
            )
        )

    def max_completion_cost_usd(self) -> Decimal:
        max_completion_len: int = (
            self.context_size - self.max_prompt_token_count()
        )
        return Decimal(
            max_completion_len
            * openai_info.get_openai_token_cost_for_model(
                model_name=self._openai.model_name,
                num_tokens=1,
                is_completion=True,
            )
        )

    def max_query_cost_usd(self) -> Decimal:
        return self.max_completion_cost_usd() + self.max_prompt_cost_usd()

    def prompt_template_token_count(
        self, prompt_file_name: str, variables: Dict[str, str]
    ) -> int:
        prompt_template: PromptTemplate = _prompt_template(prompt_file_name)
        return self._openai.get_num_tokens(prompt_template.format(**variables))

    def max_prompt_token_count(self) -> int:
        return math.floor(
            self.context_size * self._prompt_to_completion_len_ratio
        )

    @property
    @lru_cache  # Mostly to get rid of polluting logs
    def context_size(self) -> int:
        return self._infer_context_size(self._context_size_limit)

    def _infer_context_size(self, max_context_size: Optional[int]) -> int:
        inferred_context_size: Optional[int] = None
        try:
            inferred_context_size = BaseOpenAI.modelname_to_contextsize(
                self._openai.model_name
            )
        except ValueError as e:
            _LOGGER.warning(
                f"Failed to infer context size from model name. {e}"
            )
            pass

        # We need these shenanigans because langchain has a really incosistent
        # API in case of OpenAI models.
        if max_context_size and inferred_context_size:
            return min(inferred_context_size, max_context_size)
        elif max_context_size:
            return max_context_size
        elif inferred_context_size:
            return inferred_context_size

        raise ValueError(
            "Failed to infer a context size from a model name and no max "
            "context size was provided."
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
