from modules.utils import Doi
import pandas as pd
import math
from typing import List, Generator
from modules.api import Entities
import time
import aiohttp
import asyncio


class BatchProcessor:
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