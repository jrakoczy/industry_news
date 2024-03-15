from decimal import Decimal
import math
import os
from typing import Any, Callable, List, Set, Type, TypeVar
from attr import dataclass
from langchain.prompts import PromptTemplate
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_openai import OpenAI
from langchain_text_splitters import RecursiveCharacterTextSplitter
import tiktoken
from industry_news.article import SOURCE, ArticleMetadata
from industry_news.utils import load_as_string, load_resource, load_secrets


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


def _openai(filter_model: Model) -> OpenAI:
    return OpenAI(
        model_name=filter_model.name,
        openai_api_key=load_secrets()["llm"]["openai_api_key"],
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

    # TODO move whatever you can to config
    def __init__(
        self,
        filter_prompt_file_name: str = "prompt.txt",
        filter_model: Model = Model(
            name="gpt-4",
            max_prompt_length=2048,
            token_cost_usd=Decimal("30.0") / Decimal("1000000"),
            max_cost_usd=Decimal("0.1"),
            out_in_cost_ratio=Decimal("3"),
        ),
        openai_factory: Callable[[Model], OpenAI] = _openai,
    ) -> None:
        self._filter_prompt_file_name = filter_prompt_file_name
        self._filter_model = filter_model
        self._openai = openai_factory(filter_model)
        self._openai.with_structured_output(
            FilterArticlesResponse, method="json_mode"
        )

    def filter_articles(
        self, articles_metadata: List[ArticleMetadata]
    ) -> List[ArticleMetadata]:
        if not articles_metadata:
            return []

        source: SOURCE = articles_metadata[0].source
        numbered_chunks: List[str] = self._article_list_chunks(
            articles_metadata, source
        )
        remaining_titles: Set[str] = self._filter_titles(
            source, numbered_chunks
        )
        return [
            metadata
            for metadata in articles_metadata
            if metadata.title in remaining_titles
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
        return _verify_output(
            output=(prompt | self._openai).invoke(
                {"articles": articles_chunk}
            ),
            type_=FilterArticlesResponse,
        )

    def _article_list_chunks(
        self, article_metadata: List[ArticleMetadata], source: SOURCE
    ) -> List[str]:
        chunks: List[str] = _to_chunks(
            text=ArticleFiltering._to_text(article_metadata),
            chunk_size=self._max_chunk_token_count(source),
            model_name=self._filter_model.name,
        )
        cost_limited_chunks: List[str] = self._limit_cost(chunks)
        return [
            ArticleFiltering._number_lines(chunk)
            for chunk in cost_limited_chunks
        ]

    def _limit_cost(self, chunks: List[str]) -> List[str]:
        max_chunks: int = math.floor(
            self._filter_model.max_cost_usd
            / (
                self._filter_model.max_prompt_length  # TODO use context lenght and calculate this value dynamically
                #  Output tokens are more expensive:
                * (self._filter_model.out_in_cost_ratio + 1)
                * self._filter_model.token_cost_usd
            )
        )

        return chunks[:max_chunks]

    def _max_chunk_token_count(self, source: SOURCE) -> int:
        return int(
            (
                self._filter_model.max_prompt_length
                - self._prompt_template_token_count(
                    self._filter_prompt_file_name, source
                )
            )
            * 0.95  # Add some buffer for numbers at the beginning of each line
        )

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

    def _prompt_template_token_count(
        self, prompt_file_name: str, source: SOURCE
    ) -> int:
        prompt_template: PromptTemplate = _prompt_template(prompt_file_name)
        n_shot_text: str = ArticleFiltering._load_n_shot_text(source)
        return _count_tokens(
            text=prompt_template.format(examples=n_shot_text),
            model_name=self._filter_model.name,
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


def _verify_output(output: Any, type_: Type[T]) -> T:
    if not isinstance(output, type_):
        raise ValueError(f"Expected output {type_}, got {type(output)}")
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


def _count_tokens(text: str, model_name: str) -> int:
    return len(tiktoken.encoding_for_model(model_name).encode(text))
