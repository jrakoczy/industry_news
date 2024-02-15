import requests
import random
import time

RETRIES = 3
DELAY_RANGE = (1, 3)
USER_AGENT: str = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"
)


def get_with_retries(
    url: str,
    retries: int = RETRIES,
    delay_range: tuple = DELAY_RANGE,
    user_agent: str = USER_AGENT,
) -> requests.models.Response:
    for _ in range(retries - 1):
        try:
            headers: dict = {"User-Agent": USER_AGENT}
            response: requests.models.Response = requests.get(
                url=url, headers=headers
            )
            return response
        except requests.RequestException:
            delay: float = random.uniform(delay_range[0], delay_range[1])
            time.sleep(delay)
    return requests.get(url=url, headers=headers)
