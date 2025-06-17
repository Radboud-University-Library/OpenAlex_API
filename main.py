import requests
import pandas as pd
import json
from datetime import datetime
import aiohttp
import asyncio
from typing import List, Generator, AsyncGenerator
from urllib.parse import quote
import time
from email.utils import parsedate_to_datetime
from typing import Callable

radboud = "i145872427"
ror = "016xsfp80"
example_work = "W2125284466"
example_doi = "10.1111/ADB.12766"


class ApiRequestAsync:
    # Configure API class default parameters
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
                            print(f"429 Too Many Requests at: {full_url}. Retrying after {wait_time:.2f} seconds (backoff x{backoff})...")
                            await asyncio.sleep(wait_time)
                            continue
                        elif response.status == 404:
                            print(f"Error 404: Not found: {endpoint}")
                            return None
                        elif response.status != 200:
                            text = await response.text()
                            print(f"HTTP Error {response.status}: {text}")
                            response.raise_for_status()

                        return await response.json()

                except aiohttp.ClientError as e:
                    print(f"Connection error on attempt {attempt + 1}: {e}")
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


class Filter:
    @staticmethod
    def filter_attributes(filters: list[tuple[str, str]]) -> str:
        """Filter multiple attributes and return filter query string."""
        # Validate the input
        if not isinstance(filters, (list, tuple)):
            raise ValueError("Filters must be a list or tuple of key-value pairs")
        # Create filter endpoint
        filter_strings = [f"{attribute}:{value}" for attribute, value in filters]
        filter_endpoint = f"?filter=" + ",".join(filter_strings)
        return filter_endpoint


class Entities:
    def __init__(self):
        self.request = ApiRequestAsync()
        self.filter_instance = Filter()

    async def get_entity(self, endpoint: str):
        """ Get single entity """
        return await self.request.get_data(endpoint)

    async def get_multiple_entities(self, endpoint: str) -> AsyncGenerator[dict, None]:
        """Get multiple entities as an async generator."""
        results = await self.request.get_results_data(endpoint)
        for result in results:
            yield result

    async def filter(self, entity_type: str, filters: List[tuple[str, str]]) -> AsyncGenerator[dict, None]:
        """Create filter endpoint. Receives entity type from calling class."""
        if not isinstance(filters, (list, tuple)):
            raise ValueError("Filters must be a list or tuple of key-value pairs")
        endpoint = f"{entity_type}{self.filter_instance.filter_attributes(filters)}"
        return self.get_multiple_entities(endpoint)


class Works:
    def __init__(self):
        self.entities = Entities()
        self.entity = "works"

    def __getattr__(self, name):
        """ Delegates dynamic method calls to Entities class """
        return getattr(self.entities, name)

    async def filter(self, filters):
        """ Call Filter method from Entities class for list filters and adds entity type.
            Expects a tuple variable """
        return await self.entities.filter(self.entity, filters)

    def fetch_works(filters: list[tuple[str, str]]):
        """ Enter filters in a list: [("institution_id", "i145872427")] """
        async def _run():
            async with Session() as aio_session:
                request = ApiRequestAsync(session=aio_session)
                works = Works()
                works.entities.request = request
                results = []
                async for item in await works.filter(filters):
                    results.append(item)
                return results
        return asyncio.run(_run())


class Institution:
    RADBOUD_ID = "i145872427"
    RADBOUD_ROR = "016xsfp80"
    """ Nog geen functie """

    def __init__(self, institution_id=None, institution_ror=None):
        self.institution_id = institution_id or self.RADBOUD_ID
        self.ror = institution_ror or self.RADBOUD_ROR


class Json:
    @staticmethod
    def export_to_json(data, file_path):
        """ Export Json data """
        with open(file_path, "w") as file:
            json.dump(data, file, indent=4)

    @staticmethod
    def filter_json(json_data, keys_to_extract):
        """ Create list of based on selection of keys from a dict """
        # If json_data is a dictionary, wrap it in a list for uniform processing
        if isinstance(json_data, dict):
            json_data = [json_data]

        # Extract the selected keys
        json_selection = [
            {key: item[key] for key in keys_to_extract if key in item}
            for item in json_data
        ]

        # Return a single dictionary if input was a single dictionary
        return json_selection[0] if len(json_selection) == 1 else json_selection


class Doi:
    @staticmethod
    def normalize_doi(doi):
        if not isinstance(doi, str) or not doi.strip():
            raise ValueError("DOI must be a non-empty string.")
        return doi.strip().lower()

    @staticmethod
    def build_endpoint(doi):
        doi = Doi.normalize_doi(doi)
        return f"works/https://doi.org/{doi}"

    @staticmethod
    def batch_endpoint(doi_batch: List[str]) -> str:
        """Build batch endpoint while preserving | in DOIs."""
        normalized_dois = [Doi.normalize_doi(doi) for doi in doi_batch]
        encoded_dois = [quote(doi, safe="|") for doi in normalized_dois]
        doi_batch_query = "|".join(encoded_dois)
        return f"works?filter=doi:{doi_batch_query}"


class Excel:
    def __init__(self, file_path=None):
        self.file_path = file_path

    def read_excel(self, file_path):
        df = pd.read_excel(file_path)
        return df

    def write_excel(self, df, file_path, index=False):
        output_path = self.create_file_name(file_path)
        df.to_excel(output_path, index=index)

    def create_file_name(self, file_path):
        base_name = file_path.rsplit('.', 1)[0]
        current_date = datetime.now().strftime("%Y-%m-%d")
        return f"{base_name}_{current_date}.xlsx"


class Batch:
    BATCH_SIZE = 50

    def __init__(self, df: pd.DataFrame, column_name: str, works_instance: Works, batch_size: int = None):
        self.df = df
        self.column_name = column_name
        self.works_instance = works_instance
        self.batch_size = batch_size or self.BATCH_SIZE

    def generate_batches(self) -> Generator[List[str], None, None]:
        """Yield batches of DOIs from the DataFrame."""
        record_list = self.df[self.column_name].dropna().tolist()
        for i in range(0, len(record_list), self.batch_size):
            yield record_list[i:i + self.batch_size]

    async def process_single_doi(self, doi: str) -> tuple[str, dict | None]:
        """Request a single DOI if batch fails."""
        endpoint = Doi.build_endpoint(doi)
        try:
            data = await self.works_instance.get_entity(endpoint)
            return doi, data
        except Exception as e:
            print(f"Failed to fetch {doi}: {e}")
            return doi, None

    async def process_batch(self, batch: List[str]) -> List[tuple[str, dict | None]]:
        """Attempt batch fetch, fallback to singles if necessary."""
        endpoint = Doi.batch_endpoint(batch)
        try:
            response = await self.works_instance.get_entity(endpoint)
            results = response.get("results", [])
            result_map = {r.get("doi", "").lower(): r for r in results}
            return [(doi, result_map.get(doi.lower())) for doi in batch]
        except Exception as e:
            print(f"Batch failed, falling back to singles: {e}")
            return [await self.process_single_doi(doi) for doi in batch]

    async def run(
        self,
        update_fn: Callable[[pd.DataFrame, str, dict | None], None]
    ):
        """Run all batches and call update_fn for each DOI result."""
        all_batches = [self.process_batch(batch) for batch in self.generate_batches()]
        results_nested = await asyncio.gather(*all_batches)

        for batch_result in results_nested:
            for doi, result in batch_result:
                update_fn(self.df, doi, result)

if __name__ == "__main__":
    #works = Works.fetch_works([
    #    ("institutions.id", "i145872427"),
    #    ("from_publication_date", "2024-10-01"),
    #    ("is_corresponding", "true")
    #])
    #print(works)

    """ 
    Class DataExtracter/DoiEnricher maken
    Batches toevoegen
    Class Batch maken
    process single doi uit batch class halen? Dubbelop?
    """

    df = pd.read_excel("UKBsis Publication Details.xlsx")
    df = df.head(500)
    # Initialize new columns
    df["cited_by_count"] = None
    df["referenced_works_count"] = None


    async def fetch_and_prepare_result(works, doi, index):
        doi_endpoint = Doi.build_endpoint(doi)

        try:
            result = await works.get_entity(doi_endpoint)
            if result is None:
                return index, "No data", "No data"
            return index, result.get("cited_by_count"), result.get("referenced_works_count")
        except Exception as e:
            print(f"Error for DOI {doi}: {e}")
            return index, "Error", "Error"


    async def enrich_doi(df):
        async with Session(email="sjors.startman@ru.nl") as aio_session:
            request = ApiRequestAsync(session=aio_session)
            works = Works()
            works.entities.request = request  # Inject the session-bound requester

            tasks = [
                fetch_and_prepare_result(works, row['DOI'], index)
                for index, row in df.iterrows()
            ]
            results = await asyncio.gather(*tasks)

            for index, cited_by_count, referenced_works_count in results:
                df.at[index, "cited_by_count"] = cited_by_count
                df.at[index, "referenced_works_count"] = referenced_works_count


    asyncio.run(enrich_doi(df))

    # Save the updated DataFrame
    df.to_excel("UKBsis_Publication_Details_Updated.xlsx", index=False)