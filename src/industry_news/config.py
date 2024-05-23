from decimal import Decimal
from pathlib import Path
from typing import List, Optional
from pydantic import BaseModel, SecretStr
from industry_news.sources import Source
from industry_news.utils import load_as_yml

# Config


class SummaryModelConfig(BaseModel):
    name: str
    query_cost_limit_usd: Decimal
    cost_per_1k_characters_usd: Decimal
    prompt_to_completion_len_ratio: float


class FilterModelConfig(BaseModel):
    name: str
    query_cost_limit_usd: Decimal
    prompt_to_completion_len_ratio: float
    context_size_limit: int


class LLMConfig(BaseModel):
    filter_model: FilterModelConfig
    summary_model: SummaryModelConfig


class WebConfig(BaseModel):
    user_agent: str


class SingleSourceConfig(BaseModel):
    name: Source
    subspaces: List[str]


class SourcesConfig(BaseModel):
    with_summary: List[SingleSourceConfig]
    without_summary: List[SingleSourceConfig]
    articles_per_source_limit: int


class OutputConfig(BaseModel):
    digest: Path


class Config(BaseModel):
    llm: LLMConfig
    web: WebConfig
    sources: SourcesConfig
    output: OutputConfig


_config: Optional[Config] = None


def load_config() -> Config:
    global _config
    if _config is None:
        _config = Config(**load_as_yml("config.yml"))
    return _config


# Secrets


class LLMSecrets(BaseModel):
    openai_api_key: SecretStr
    service_account_file_path: Path


class RedditSecrets(BaseModel):
    client_id: str
    client_secret: SecretStr


class Secrets(BaseModel):
    reddit: RedditSecrets
    llm: LLMSecrets


_secrets: Optional[Secrets] = None


def load_secrets() -> Secrets:
    global _secrets
    if _secrets is None:
        _secrets = Secrets(**load_as_yml("secrets.yml"))
    return _secrets
