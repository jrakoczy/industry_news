import logging
from pathlib import Path
from typing import Any, Dict, Optional, Type, TypeVar, Tuple
from httplib2 import RETRIES
import requests
from furl import furl
from urllib.parse import urlparse, ParseResult
from industry_news.utils import retry
from industry_news.utils import to_file_backup
from industry_news.utils import from_file_backup

DELAY_RANGE_S: Tuple[float, float] = (1.0, 3.0)
USER_AGENT: str = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    + "(KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"
)
_LOGGER = logging.getLogger(__name__)


T = TypeVar("T")
R = TypeVar("R")


def modify_url_query(
    url: ParseResult, query_params: Dict[str, str]
) -> ParseResult:
    mutable_url: furl = furl(url.geturl())
    mutable_url.args.update(query_params)
    return urlparse(mutable_url.url)


def construct_url(
    base_url: str, relative_path: str, query_params: Dict[str, str] = {}
) -> ParseResult:
    url: furl = furl(base_url)
    url /= relative_path
    url.args = query_params
    return urlparse(url.url)


def base_url_str(url: ParseResult) -> str:
    return furl(url.geturl()).origin


def verify_page_element(element: Optional[T], type_: Type[R]) -> R:
    if not isinstance(element, type_):
        raise ValueError("Invalid page element.")
    return element


def get_with_retries(
    url: ParseResult,
    delay_range_s: Tuple[float, float] = DELAY_RANGE_S,
    user_agent: str = USER_AGENT,
    retries: int = RETRIES,
) -> requests.models.Response:
    headers: dict = {"User-Agent": user_agent}
    return retry(
        lambda: requests.get(url.geturl(), headers), delay_range_s, retries
    )


def get_json_with_backup(
    url: ParseResult,
    filepath: Path,
    delay_range_s: Tuple[float, float] = DELAY_RANGE_S,
    user_agent: str = USER_AGENT,
    retries: int = RETRIES,
) -> dict[str, Any]:
    """
    Since retrieval from the API is comparitvely very slow, we store fetched
    items locally. In case of any failures when can retrieve them much
    quicker than sending the same HTTP request again.
    """
    data_from_file: Optional[dict[str, Any]] = from_file_backup(filepath)
    item_data: dict[str, Any]

    if data_from_file:
        _LOGGER.info(f"Loaded from a backup file: {filepath}")
        item_data = data_from_file
    else:
        item_data = get_with_retries(
            url, delay_range_s, user_agent, retries
        ).json()

    to_file_backup(filepath, item_data)
    return item_data
