import pandas as pd
import json
from datetime import datetime
import aiohttp
import asyncio
from typing import List, Generator, Awaitable, Callable
import time
from email.utils import parsedate_to_datetime
import math


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
                            print(f"429 Too Many Requests at: {full_url}. Retrying after {wait_time:.2f}s...")
                            await asyncio.sleep(wait_time)
                            continue

                        # Raise for all HTTP errors (including 404)
                        response.raise_for_status()

                        # Success
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

        # If all retries fail:
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
    def __init__(self, entity_type: str, request=None):
        self.entity_type = entity_type
        self.request = request or ApiRequestAsync()
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
                request = ApiRequestAsync(session=aio_session)
                entities = Entities("works", request=request)
                return await entities.get(input)
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
        return doi.strip().lower().rstrip('.')

    @staticmethod
    def build_endpoint(doi):
        doi = Doi.normalize_doi(doi)
        return f"works/https://doi.org/{doi}"

    @staticmethod
    def batch_endpoint(dois: List[str]) -> str:
        doi_filter = "|".join([doi.strip() for doi in dois])
        return f"?filter=doi:{doi_filter}"


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
    BATCH_SIZE = 25

    def __init__(self, df: pd.DataFrame, column_name: str, entities_instance: Entities, batch_size: int = None):
        self.df = df
        self.column_name = column_name
        self.entities = entities_instance
        self.batch_size = batch_size or self.BATCH_SIZE
        self.total_processed = 0
        self.total_dois = len(list(dict.fromkeys(self.df[self.column_name].dropna().tolist())))
        self.start_time = time.time()

    def generate_batches(self) -> Generator[List[str], None, None]:
        record_list = list(dict.fromkeys(self.df[self.column_name].dropna().tolist()))
        for i in range(0, len(record_list), self.batch_size):
            yield record_list[i:i + self.batch_size]

    async def retry_single_doi(self, doi: str) -> tuple[str, dict | None | str]:
        doi_norm = Doi.normalize_doi(doi)

        try:
            single_result = await self.entities.get(doi)

            if single_result:
                return (doi_norm, single_result)
            else:
                return (doi_norm, "invalid input")

        except aiohttp.ClientResponseError as e2:
            if e2.status == 404:
                return (doi_norm, "404 error")
            else:
                print(f"HTTP error {e2.status} for DOI {doi_norm}")
                return (doi_norm, None)

        except Exception as ex:
            print(f"Retry failed for DOI {doi_norm}: {ex}")
            return (doi_norm, None)

    async def process_batch(self, batch: List[str]) -> List[tuple[str, dict | None | str]]:
        batch_start = time.time()
        updated_batch = []

        try:
            results = await self.entities.get(batch)

            result_map = {
                r.get("doi", "").lower().replace("https://doi.org/", ""): r
                for r in results
            }

            for doi in batch:
                doi_norm = Doi.normalize_doi(doi)
                result = result_map.get(doi_norm)

                if result is not None:
                    updated_batch.append((doi_norm, result))
                else:
                    updated_batch.append(await self.retry_single_doi(doi))

        except Exception as e:
            print(f"Batch failed: {e} — retrying DOIs individually...")
            updated_batch = [await self.retry_single_doi(doi) for doi in batch]

        # update progress
        self.total_processed += len(batch)
        elapsed = time.time() - self.start_time
        avg_time_per_doi = elapsed / self.total_processed if self.total_processed else 0
        remaining_dois = self.total_dois - self.total_processed
        eta_minutes = math.ceil(remaining_dois * avg_time_per_doi / 60)

        print(f"Finished batch: {self.total_processed}/{self.total_dois} DOIs processed "
              f"(Batch time: {time.time() - batch_start:.1f}s, ETA: {eta_minutes} min)")

        return updated_batch

    async def run(self, update_fn):
        for batch in self.generate_batches():
            success = False
            retries = 0
            max_retries = 3

            while not success and retries < max_retries:
                batch_results = await self.process_batch(batch)

                if batch_results is not None:
                    for doi, result in batch_results:
                        await update_fn(self.df, doi, result)

                    success = True

                else:
                    retries += 1
                    print(f"Retrying batch ({retries}/{max_retries})...")
                    await asyncio.sleep(2 ** retries)


if __name__ == "__main__":
    #work = Works.get("W2125284466")
    #print(work)
    #works = Works.get([
    #   ("institutions.id", "i145872427"),
    #   ("from_publication_date", "2024-10-01"),
    #    ("is_corresponding", "true")
    #])
    #print(works)
    #doi_list = Works.get([
    #"10.1016/J.PATTER.2022.100639",
    #"10.1016/J.TRECAN.2024.08.008"
    #])
    #print(doi_list)
    """ 
    NO result opvangen
    """

    df = pd.read_excel("UKBsis Publication Details.xlsx")
    df = df.iloc[10000:20000]

    # Initialize new columns
    df["cited_by_count"] = None
    df["referenced_works_count"] = None


    # Define update_fn
    async def update_fn(df: pd.DataFrame, doi: str, result: dict | None | str):
        doi_normalized = doi.strip().lower()

        # Add normalized column (do this only once if not already present)
        if "DOI_normalized" not in df.columns:
            df["DOI_normalized"] = df["DOI"].astype(str).apply(Doi.normalize_doi)

        matching_rows = df[df["DOI_normalized"] == doi_normalized]

        if matching_rows.empty:
            print(f"No match found in DataFrame for DOI: {doi}")
            return

        elif result == "404 error":
            df.loc[matching_rows.index, "cited_by_count"] = "URL not found"
            df.loc[matching_rows.index, "referenced_works_count"] = "URL not found"

        else:
            # Valid result, update cited_by_count and referenced_works_count
            df.loc[matching_rows.index, "cited_by_count"] = result.get("cited_by_count")
            df.loc[matching_rows.index, "referenced_works_count"] = result.get("referenced_works_count")


    # Main async runner
    async def enrich_with_batches(df: pd.DataFrame):
        async with Session() as aio_session:
            request = ApiRequestAsync(session=aio_session)
            entities = Entities("works", request=request)

            batcher = Batch(df=df, column_name="DOI", entities_instance=entities)
            await batcher.run(update_fn=update_fn)


    # Run
    asyncio.run(enrich_with_batches(df))

    # Save the updated DataFrame
    df.to_excel("UKBsis_Publication_Details_Updated.xlsx", index=False)