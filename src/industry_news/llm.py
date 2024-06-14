from dataclasses import replace
from decimal import Decimal
from functools import lru_cache, wraps
import logging
import math
import os
from pathlib import Path
from typing import (
    Any,
    Callable,
    Dict,
    Generator,
    List,
    Optional,
    Type,
    TypeVar,
)
from langchain.prompts import PromptTemplate
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_community.callbacks import openai_info, manager
from langchain_google_vertexai import VertexAI
from langchain_openai import ChatOpenAI
from langchain_openai.llms.base import BaseOpenAI
from langchain_text_splitters import RecursiveCharacterTextSplitter
from industry_news.digest.article import ArticleMetadata, ArticleSummary
from industry_news.config import (
    FilterModelConfig,
    SummaryModelConfig,
    load_config,
    load_secrets,
)
from industry_news.sources import Source
from industry_news.utils import (
    fail_gracefully,
    load_as_string,
    load_resource,
)

_LOGGER = logging.getLogger(__name__)
_PROMPT_PATH = "prompts"
_NUM_OF_DIFFERENT_MODELS = 2
T = TypeVar("T")


class TextSummarizer:

    @staticmethod
    def _vertex_ai(model_name: str) -> VertexAI:
        service_account_env = "GOOGLE_APPLICATION_CREDENTIALS"

        os.environ[service_account_env] = str(
            load_secrets().llm.service_account_file_path
        )
        vertex_ai = VertexAI(max_retries=3, model=model_name)
        os.environ.pop(service_account_env)

        return vertex_ai

    def __init__(
        self,
        summary_prompt_file_name: str = (
            f"{load_config().digest.name}/{_PROMPT_PATH}/summarize_prompt.txt"
        ),
        config: SummaryModelConfig = load_config().llm.summary_model,
        vertex_ai_factory: Callable[[str], VertexAI] = _vertex_ai,
    ) -> None:
        self._summary_prompt_file_name = summary_prompt_file_name
        self._config = config
        self._model = _prompt_template(
            summary_prompt_file_name
        ) | vertex_ai_factory(config.name)

    def summarize(
            self, text_generator: Generator[str, None, None]
    ) -> List[str]:
        """
        Args:
            text_generator: Use a generator to delegate loading text logic to a
            method's caller and to avoid loading all text into memory at once.
        """
        summaries: List[str] = []
        total_cost_usd: Decimal = Decimal(0)

        for text in text_generator:
            total_cost_usd += self._text_cost(text)
            if total_cost_usd > self._config.query_cost_limit_usd:
                break

            summary: Optional[str] = self._invoke_model(text)
            summaries.append(summary if summary else "Failed to summarize.")

        TextSummarizer._log_total_cost(total_cost_usd)
        return summaries

    def _invoke_model(self, text: str) -> Optional[str]:
        output: Optional[Any] = fail_gracefully(
            lambda: self._model.invoke({"text": text})
        )
        return _verify_output(output=output, type_=str) if output else None

    @staticmethod
    def _log_total_cost(total_cost_usd: Decimal) -> None:
        _LOGGER.info(
            "Est. total cost of summarization: %.3f USD.",
            float(total_cost_usd),
        )

    def _text_cost(self, text: str) -> Decimal:
        completion_to_prompt_len_ratio = Decimal(
            1.0 / self._config.prompt_to_completion_len_ratio
        )
        prompt_cost_usd: Decimal = (
                Decimal(len(text) + self._prompt_char_len())
                / Decimal(1000)  # Cost is per 1k chars
                * self._config.cost_per_1k_characters_usd
        )

        return (
                prompt_cost_usd + prompt_cost_usd * completion_to_prompt_len_ratio
        )

    @lru_cache
    def _prompt_char_len(self) -> int:
        return len(load_as_string(self._summary_prompt_file_name))


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
    _OPENAI_FACTORY: Callable[[str], ChatOpenAI] = (
        lambda model_name: ChatOpenAI(
            max_retries=3,
            model_name=model_name,
            openai_api_key=load_secrets().llm.openai_api_key.get_secret_value(),
        )
    )

    def __init__(
            self,
            config: FilterModelConfig = load_config().llm.filter_model,
            prompt_dir: Path = Path(load_config().digest.name) / _PROMPT_PATH,
            filter_prompt_file_name: str = "filter_prompt.txt",
            openai_factory: Callable[[str], ChatOpenAI] = _OPENAI_FACTORY,
    ) -> None:
        openai_model: ChatOpenAI = openai_factory(config.name)
        self._prompt_dir = prompt_dir
        self._filter_prompt_file_path = self._prompt_dir / filter_prompt_file_name
        self._model_name = openai_model.model_name
        self._model = _prompt_template(
            f"{self._prompt_dir}/{filter_prompt_file_name}"
        ) | openai_model.with_structured_output(
            FilterArticlesResponse, method="json_mode"
        )
        self._query_cost_limit_usd = config.query_cost_limit_usd
        self._cost_calculator = OpenAICostCalculator(
            openai=openai_model,
            prompt_to_completion_len_ratio=(
                config.prompt_to_completion_len_ratio
            ),
            context_size_limit=config.context_size_limit,
        )

    def filter_summaries(
            self, articles_summaries: List[ArticleSummary]
    ) -> List[ArticleSummary]:
        """
        Filters the list of articles based on criteria defined in a prompt.

        Returns:
            List[ArticleMetadata]: A returned list is sorted in descending
            order by score.
        """
        if not articles_summaries:
            return []

        source: Source = articles_summaries[0].metadata.source

        sorted_articles: List[ArticleSummary] = self._sort_summaries_by_score(
            articles_summaries
        )
        remaining_titles: Dict[str, str] = self._filter_by_titles(
            source, [summary.metadata for summary in sorted_articles]
        )

        return ArticleFiltering._filter_summaries_adding_reasons(
            sorted_articles, remaining_titles
        )

    def filter_metadata(
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
        self._log_estimated_cost(source)

        sorted_articles_metadata: List[ArticleMetadata] = (
            self._sort_metadata_by_score(articles_metadata)
        )

        remaining_titles: Dict[str, str] = self._filter_by_titles(
            source, sorted_articles_metadata
        )

        return ArticleFiltering._filter_metadata_adding_reasons(
            sorted_articles_metadata, remaining_titles
        )

    def _log_estimated_cost(self, source: Source) -> None:
        _LOGGER.info(
            "Filtering %s articles. Estimated maximum query cost: %.3f USD.",
            source.value,
            float(self._cost_calculator.max_query_cost_usd()),
        )

    def _sort_summaries_by_score(
            self, articles_summaries: List[ArticleSummary]
    ) -> List[ArticleSummary]:
        return sorted(
            articles_summaries,
            key=lambda summary: summary.metadata.score,
            reverse=True,
        )

    def _sort_metadata_by_score(
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

    @staticmethod
    def _with_openai_cost_logged(
            func: Callable[..., Any]
    ) -> Callable[..., Any]:
        @wraps(func)
        def wrapper(
                self: Any, *args: List[Any], **kwargs: Dict[Any, Any]
        ) -> Any:
            with manager.get_openai_callback() as openai_callback:
                result = func(self, *args, **kwargs)
                _LOGGER.info(openai_callback)
            return result

        return wrapper

    def _filter_by_titles(
            self,
            source: Source,
            articles_metadta: List[ArticleMetadata],
    ) -> Dict[str, str]:
        article_titles_chunks: List[str] = self._titles_to_chunks(
            articles_metadta, source
        )
        remaining_titles: Dict[str, str] = self._filter_titles_by_prompt(
            source, article_titles_chunks
        )

        return remaining_titles

    @_with_openai_cost_logged
    def _filter_titles_by_prompt(
            self, source: Source, numbered_chunks: List[str]
    ) -> Dict[str, str]:
        """
        Returns:
            Dict[str, str]: [Title, Reason why an article was selected]
        """
        remaining_titles_dict: Dict[str, str] = dict()

        for articles_chunk in numbered_chunks:
            response: FilterArticlesResponse = self._invoke_model(
                source, articles_chunk
            )
            remaining_titles_dict.update(
                self._filter_titles_chunk(articles_chunk, response)
            )

        return remaining_titles_dict

    def _invoke_model(
            self,
            source: Source,
            articles_chunk: str,
    ) -> FilterArticlesResponse:
        prompt_variables: Dict[str, str] = ArticleFiltering._prompt_variables(
            source, articles_chunk
        )
        output: Any = self._model.invoke(prompt_variables)
        return _verify_output(output=output, type_=FilterArticlesResponse)

    @staticmethod
    def _filter_titles_chunk(
            articles_titles_chunk: str, model_response: FilterArticlesResponse
    ) -> Dict[str, str]:
        return {
            ArticleMetadata.title_from_description(
                line
            ): model_response.reasonings[i]
            for i, line in enumerate(articles_titles_chunk.split(os.linesep))
            if i + 1 in model_response.relevant_articles
        }

    def _titles_chunk_max_token_count(self, source: Source) -> int:
        prompt_variables: Dict[str, str] = ArticleFiltering._prompt_variables(
            source, ""
        )
        template_token_count: int = (
            self._cost_calculator.prompt_template_token_count(
                self._filter_prompt_file_path, prompt_variables
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
            * 0.95,  # Lazy solution to avoid exceeding context size after
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
            [f"{i + 1}. {line}" for i, line in enumerate(text.split(os.linesep))]
        )

    @lru_cache
    def _load_n_shot_text(self, source: Source) -> str:
        return load_as_string(
            f"{self._prompt_dir}/n_shot/{source.value}_n_shot.txt"
        )

    @staticmethod
    def _filter_metadata_adding_reasons(
            sorted_articles_metadata: List[ArticleMetadata],
            remaining_titles_dict: Dict[str, str],
    ) -> List[ArticleMetadata]:
        remaining_metadata: List[ArticleMetadata] = []

        for metadata in sorted_articles_metadata:
            if metadata.title in remaining_titles_dict.keys():
                metadata_with_reason: ArticleMetadata = replace(
                    metadata,
                    why_is_relevant=remaining_titles_dict[metadata.title],
                )
                remaining_metadata.append(metadata_with_reason)

        return remaining_metadata

    @staticmethod
    def _filter_summaries_adding_reasons(
            sorted_articles_summaries: List[ArticleSummary],
            remaining_titles_dict: Dict[str, str],
    ) -> List[ArticleSummary]:
        remaining_summaries: List[ArticleSummary] = []

        for summary in sorted_articles_summaries:
            if summary.metadata.title in remaining_titles_dict.keys():
                summary_with_reason: ArticleSummary = replace(
                    summary,
                    metadata=replace(
                        summary.metadata,
                        why_is_relevant=remaining_titles_dict[
                            summary.metadata.title
                        ],
                    ),
                )
                remaining_summaries.append(summary_with_reason)

        return remaining_summaries


class OpenAICostCalculator:
    def __init__(
            self,
            openai: ChatOpenAI,
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


@lru_cache(maxsize=_NUM_OF_DIFFERENT_MODELS)
def _prompt_template(prompt_file_name: str) -> PromptTemplate:
    return PromptTemplate.from_file(load_resource(prompt_file_name))
