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
        """ Initialize API request """
        self.base_url = base_url or self.BASE_URL
        self.per_page = self.PER_PAGE
        self.semaphore = semaphore or asyncio.Semaphore(self.SEMAPHORE)
        self.last_request_time = self.LAST_REQUEST_TIME
        self.min_interval = min_interval or self.MIN_INTERVAL
        self.session = session

    def full_url(self, endpoint):
        """ Build full url """
        return f"{self.base_url}{endpoint}"

    async def get_data(self, endpoint):
        full_url = self.full_url(endpoint)

        async with self.semaphore:
            now = time.monotonic()
            elapsed = now - self.last_request_time
            if elapsed < self.min_interval:
                await asyncio.sleep(self.min_interval - elapsed)
            self.last_request_time = time.monotonic()

            for attempt in range(3):
                try:
                    async with self.session.get(full_url) as response:
                        if response.status == 429:
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
                            continue

                        response.raise_for_status()

                        return await response.json()

                except aiohttp.ClientResponseError as e:
                    if e.status == 404:
                        print(f"HTTP error {e.status}: {e.message}. {endpoint}")
                        raise
                    else:
                        print(f"HTTP error {e.status}: {e.message}. {endpoint} (attempt {attempt + 1})")
                        await asyncio.sleep(1 + attempt)

                except aiohttp.ClientError as e:
                    print(f"Connection error (attempt {attempt + 1}): {e}")
                    await asyncio.sleep(1 + attempt)

        return None

    async def get_meta_data(self, endpoint):
        data = await self.get_data(endpoint)
        return data.get("meta") if data else None

    async def get_results_data(self, endpoint):
        cursor = "*"
        data = []

        while True:
            paged_endpoint = f"{endpoint}&per_page={self.per_page}&cursor={cursor}"
            response = await self.get_data(paged_endpoint)
            if not response:
                break

            data.extend(response.get('results', []))
            cursor = response.get('meta', {}).get('next_cursor')
            if not cursor:
                break

        return data

class Filter:
    @staticmethod
    def filter_attributes(filters: list[tuple[str, str]]) -> str:
        """Filter multiple attributes and return filter query string."""

        if not isinstance(filters, (list, tuple)):
            raise ValueError("Filters must be a list or tuple of key-value pairs")

        filter_strings = [f"{attribute}:{value}" for attribute, value in filters]
        filter_endpoint = f"?filter=" + ",".join(filter_strings)
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
            if input.lower().startswith("10."):
                endpoint = Doi.build_endpoint(input)
                return await self.request.get_data(endpoint)
            else:
                endpoint = f"{self.entity_type}/{input}"
                return await self.request.get_data(endpoint)

        elif isinstance(input, list):
            if all(isinstance(i, tuple) for i in input):
                endpoint = f"{self.entity_type}{self.filter_instance.filter_attributes(input)}"
                results = await self.request.get_results_data(endpoint)
                return results

            elif all(isinstance(i, str) for i in input):
                endpoint = f"{self.entity_type}{Doi.batch_endpoint(input)}"
                results = await self.request.get_data(endpoint)
                return results.get("results", []) if results else []

            else:
                raise ValueError("Unsupported input list type for get()")

        else:
            raise ValueError("Unsupported input type for get()")


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