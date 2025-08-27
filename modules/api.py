import aiohttp, socket, brotli
import asyncio
import time
from email.utils import parsedate_to_datetime
from datetime import datetime
from dotenv import load_dotenv
import os
import orjson

load_dotenv()

class ApiClient:
    BASE_URL = "https://api.openalex.org/"
    PER_PAGE = "100"
    SEMAPHORE = 3
    LAST_REQUEST_TIME = 0
    MIN_INTERVAL = 0.5

    def __init__(self, base_url=None, semaphore=None, min_interval=None, session: aiohttp.ClientSession = None):
        self.base_url = base_url or self.BASE_URL
        self.per_page = self.PER_PAGE
        self.semaphore = semaphore or asyncio.Semaphore(self.SEMAPHORE)
        self.last_request_time = self.LAST_REQUEST_TIME
        self.min_interval = min_interval or self.MIN_INTERVAL
        self.session = session

    def _full_url(self, endpoint):
        return f"{self.base_url}{endpoint}"

    async def get_data(self, endpoint):
        full_url = self._full_url(endpoint)
        async with self.semaphore:
            await self._respect_rate_limit()
            for attempt in range(3):
                try:
                    return await self._attempt_request(full_url, attempt)
                except Exception as e:
                    await self._handle_attempt_exception(e, attempt, full_url)
        return None

    async def _respect_rate_limit(self):
        now = time.monotonic()
        elapsed = now - self.last_request_time
        if elapsed < self.min_interval:
            await asyncio.sleep(self.min_interval - elapsed)
        self.last_request_time = time.monotonic()

    async def _attempt_request(self, full_url, attempt):
        async with self.session.get(full_url) as response:
            if response.status == 429:
                await self._handle_rate_limit(response, attempt, full_url)
                raise Exception("Retry after rate limit")
            response.raise_for_status()
            return await response.json(loads=orjson.loads)

    async def _handle_rate_limit(self, response, attempt, full_url):
        retry_after = response.headers.get("Retry-After", "1")
        try:
            wait_time = int(retry_after)
        except ValueError:
            retry_dt = parsedate_to_datetime(retry_after)
            now_dt = datetime.now(retry_dt.tzinfo)
            wait_time = max((retry_dt - now_dt).total_seconds(), 1)
        backoff = 2 ** attempt
        wait_time += backoff
        print(f"429 Too Many Requests at: {full_url}. Retrying after {wait_time:.2f}s...")
        await asyncio.sleep(wait_time)

    async def _handle_attempt_exception(self, e, attempt, full_url):
        if isinstance(e, aiohttp.ClientResponseError):
            if e.status == 404:
                print(f"HTTP error {e.status}: {e.message}. {full_url}")
                raise
            else:
                print(f"HTTP error {e.status}: {e.message}. {full_url} (attempt {attempt + 1})")
                await asyncio.sleep(1 + attempt)
        elif isinstance(e, aiohttp.ClientError):
            print(f"Connection error (attempt {attempt + 1}): {e}")
            await asyncio.sleep(1 + attempt)

    async def get_meta_data(self, endpoint):
        data = await self.get_data(endpoint)
        return data.get("meta") if data else None

    async def get_results_data(self, endpoint):
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

    def _build_paged_endpoint(self, endpoint, cursor):
        sep = "&" if "?" in endpoint else "?"
        return f"{endpoint}{sep}per_page={self.per_page}&cursor={cursor}"

    async def get_url(self, url: str):
        if not url.startswith(self.base_url):
            print(f"Invalid OpenAlex URL: {url}")
            return None
        url = url.replace(self.base_url,"")
        has_query = any(param in url for param in ["filter=", "search=", "cursor=", "per_page="])
        if has_query:
            data = await self.get_results_data(url)
        else:
            data = await self.get_data(url)
        return data

    def get_select(self, endpoint: str, select_list) -> str:
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

class Session:
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
            #data = await api.get_data("works/W2125284466")
            data = await api.get_results_data("works?filter=cites:W2058595066")
            print(data)
            #print(type(data))
            #print(len(data))
    asyncio.run(main())