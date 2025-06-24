import aiohttp
import asyncio
import time
from email.utils import parsedate_to_datetime
from datetime import datetime
from modules.utils import Doi


class ApiRequest:
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

    def full_url(self, endpoint):
        return f"{self.base_url}{endpoint}"

    async def get_data(self, endpoint):
        full_url = self.full_url(endpoint)
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
            return await response.json()

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
        return f"{endpoint}&per_page={self.per_page}&cursor={cursor}"


class Filter:
    @staticmethod
    def filter_attributes(filters: list[tuple[str, str]]) -> str:
        if not isinstance(filters, (list, tuple)):
            raise ValueError("Filters must be a list or tuple of key-value pairs")

        filter_strings = [f"{attribute}:{value}" for attribute, value in filters]
        filter_endpoint = "?filter=" + ",".join(filter_strings)
        return filter_endpoint


class Session:
    EMAIL = "sjors.startman@ru.nl"

    def __init__(self, email=None):
        self.session = None
        self.email = email or self.EMAIL

    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            headers={"User-Agent": f"mailto:{self.email}"}
        )
        return self.session

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.session.close()


class Entities:
    def __init__(self, entity_type: str, request=None):
        self.entity_type = entity_type
        self.request = request or ApiRequest()
        self.filter_instance = Filter()

    async def get(self, input):
        if isinstance(input, str):
            return await self._get_from_string(input)
        elif isinstance(input, list):
            return await self._get_from_list(input)
        else:
            raise ValueError("Unsupported input type for get()")

    async def _get_from_string(self, input):
        if input.lower().startswith("10."):
            endpoint = Doi.build_endpoint(input)
        else:
            endpoint = f"{self.entity_type}/{input}"
        return await self.request.get_data(endpoint)

    async def _get_from_list(self, input_list):
        if all(isinstance(i, tuple) for i in input_list):
            endpoint = f"{self.entity_type}{self.filter_instance.filter_attributes(input_list)}"
            return await self.request.get_results_data(endpoint)
        elif all(isinstance(i, str) for i in input_list):
            endpoint = f"{self.entity_type}{Doi.batch_endpoint(input_list)}"
            response = await self.request.get_data(endpoint)
            return response.get("results", []) if response else []
        else:
            raise ValueError("Unsupported input list type for get()")


class Works:
    def __init__(self, request=None):
        self.entities = Entities("works", request=request)

    def __getattr__(self, name):
        return getattr(self.entities, name)

    @staticmethod
    def get(input):
        async def _run():
            async with Session() as aio_session:
                request = ApiRequest(session=aio_session)
                entities = Entities("works", request=request)
                return await entities.get(input)
        return asyncio.run(_run())


if __name__ == "__main__":
    work = Works.get("W2125284466")
    print(work)