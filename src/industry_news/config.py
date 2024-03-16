from decimal import Decimal
from pydantic import BaseModel

from industry_news.utils import load_as_yml

# Config


class FilterModelConfig(BaseModel):
    name: str
    max_query_cost_usd: Decimal
    prompt_to_completion_len_ratio: float


class LLMConfig(BaseModel):
    filter_model: FilterModelConfig


class WebConfig(BaseModel):
    user_agent: str


class Config(BaseModel):
    llm: LLMConfig
    web: WebConfig


def load_config() -> Config:
    return Config(**load_as_yml("config.yml"))


# Secrets


class LLMSecrets(BaseModel):
    openai_api_key: str


class RedditSecrets(BaseModel):
    client_id: str
    client_secret: str


class Secrets(BaseModel):
    reddit: RedditSecrets
    llm: LLMSecrets


def load_secrets() -> Secrets:
    return Secrets(**load_as_yml("secrets.yml"))
