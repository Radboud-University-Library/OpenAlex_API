import aiohttp
import socket
import asyncio
import time
from email.utils import parsedate_to_datetime
from datetime import datetime
from dotenv import load_dotenv
import os
import orjson
from modules.utils import Keys

load_dotenv()


class ApiClient:
    BASE_URL = "https://api.openalex.org/"
    PER_PAGE = "200"
    SEMAPHORE = 8
    LAST_REQUEST_TIME = 0
    MIN_INTERVAL = 0.1

    def __init__(
        self,
        base_url: str = None,
        semaphore: asyncio.Semaphore = None,
        min_interval: float = None,
        session: aiohttp.ClientSession = None
    ):
        """
        Initialize the API client for OpenAlex.
        """
        self.base_url = base_url or self.BASE_URL
        self.per_page = self.PER_PAGE
        self.semaphore = semaphore or asyncio.Semaphore(self.SEMAPHORE)
        self.last_request_time = self.LAST_REQUEST_TIME
        self.min_interval = min_interval or self.MIN_INTERVAL
        self.session = session
        self._global_backoff_until = 0
        self._last_logged_backoff = 0

    async def get_data(self, endpoint: str) -> dict | None:
        """
        Fetch a single page of data from the given endpoint.
        """
        full_url = self._full_url(endpoint)
        async with self.semaphore:
            await self._respect_rate_limit()
            for attempt in range(3):
                try:
                    return await self._attempt_request(full_url)
                except Exception as e:
                    await self._handle_attempt_exception(e, attempt, full_url)
        return None

    async def get_results_data(self, endpoint: str) -> list[dict]:
        """
        Fetch paginated results from an endpoint using cursors.
        """
        cursor = "*"
        all_results = []
        while cursor:
            paged_endpoint = self._build_paged_endpoint(endpoint, cursor)
            response = await self.get_data(paged_endpoint)
            if not response:
                break
            all_results.extend(response.get("results", []))
            cursor = response.get("meta", {}).get("next_cursor")
        return all_results

    async def get_url(self, url: str, select_list: list[str] = None) -> dict | list | None:
        """
        Resolve a full OpenAlex URL to data (single page or paginated depending on query).
        """
        if not url.startswith(self.base_url):
            print(f"Invalid OpenAlex URL: {url}")
            return None

        endpoint = url.replace(self.base_url, "")
        if select_list:
            select_list = Keys.root_keys(select_list)
            endpoint = self.get_select(endpoint, select_list)

        if self._is_query_url(endpoint):
            return await self.get_results_data(endpoint)
        return await self.get_data(endpoint)

    def get_select(self, endpoint: str, select_list: list[str] | str) -> str:
        """
        Add a `select=` parameter to an endpoint to limit returned fields.
        """
        if isinstance(select_list, (list, tuple)):
            if not select_list:
                raise ValueError("select_list cannot be empty")
            fields = ",".join(select_list)
        elif isinstance(select_list, str):
            fields = select_list.strip()
            if not fields:
                raise ValueError("select_list cannot be empty")
        else:
            raise TypeError(f"Invalid input type {type(select_list)}. Expected list[str] or str.")

        sep = "&" if "?" in endpoint else "?"
        return f"{endpoint}{sep}select={fields}"

    async def resolve_api_url(self, url: str, projection: str | None = None, keys: list[str] = None):
        """
        Fetch data from a single OpenAlex API URL and return the projected value (if any).
        """
        if not url.startswith(self.base_url):
            print(f"Invalid OpenAlex URL: {url}")
            return None

        try:
            data = await self.get_url(url, keys)
            return Keys.project_keys(data, projection)
        except Exception as e:
            print(f"Failed to resolve {url}: {e}")
            return None

    def _is_query_url(self, endpoint: str) -> bool:
        return any(param in endpoint for param in ["filter=", "search=", "cursor=", "per_page="])

    async def _respect_rate_limit(self):
        now = time.monotonic()

        if now < self._global_backoff_until:
            await asyncio.sleep(self._global_backoff_until - now)

        elapsed = now - self.last_request_time
        if elapsed < self.min_interval:
            await asyncio.sleep(self.min_interval - elapsed)

        self.last_request_time = time.monotonic()

    async def _attempt_request(self, full_url: str):
        async with self.session.get(full_url) as response:
            if response.status == 429:
                await self._handle_rate_limit(response, full_url)
                raise Exception("Retry after rate limit")
            response.raise_for_status()
            return await response.json(loads=orjson.loads)

    async def _handle_rate_limit(self, response: aiohttp.ClientResponse, full_url: str):
        retry_after = response.headers.get("Retry-After", "1")
        try:
            wait_time = int(retry_after)
        except ValueError:
            retry_dt = parsedate_to_datetime(retry_after)
            now_dt = datetime.now(retry_dt.tzinfo)
            wait_time = max((retry_dt - now_dt).total_seconds(), 1)
        self._global_backoff_until = time.monotonic() + wait_time
        self._last_logged_backoff = self._global_backoff_until
        await asyncio.sleep(wait_time)

    async def _handle_attempt_exception(self, e: Exception, attempt: int, full_url: str):
        if isinstance(e, aiohttp.ClientResponseError):
            if e.status == 404:
                print(f"HTTP 404 Not Found: {full_url}")
                raise
            else:
                print(f"HTTP error {e.status}: {e.message}. Retrying (attempt {attempt + 1})")
                await asyncio.sleep(1 + attempt)
        elif isinstance(e, aiohttp.ClientError):
            print(f"Connection error (attempt {attempt + 1}): {e}")
            await asyncio.sleep(1 + attempt)

    def _build_paged_endpoint(self, endpoint: str, cursor: str) -> str:
        sep = "&" if "?" in endpoint else "?"
        return f"{endpoint}{sep}per_page={self.per_page}&cursor={cursor}"

    def _full_url(self, endpoint: str) -> str:
        return f"{self.base_url}{endpoint}"


class Session:
    """
    Context manager for aiohttp.ClientSession with OpenAlex-friendly headers.
    """
    def __init__(self, email=None):
        self.session = None
        self.email = email or os.getenv("OPENALEX_EMAIL")

    async def __aenter__(self):
        connector = aiohttp.TCPConnector(
            limit=0,
            ttl_dns_cache=300,
            family=socket.AF_INET,
            enable_cleanup_closed=True,
        )
        self.session = aiohttp.ClientSession(
            connector=connector,
            headers={
                "User-Agent": f"mailto:{self.email}",
                "Accept-Encoding": "gzip, deflate, br",
            },
        )
        return self.session

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.session.close()


if __name__ == "__main__":
    async def main():
        async with Session() as aio_session:
            api = ApiClient(session=aio_session)
            data = await api.get_results_data("works?filter=cites:W2058595066")
            print(data)
    asyncio.run(main())
