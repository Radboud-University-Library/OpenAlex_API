from __future__ import annotations
from modules.utils import Doi
import pandas as pd
import math
from typing import List, Generator
import time
import aiohttp
import asyncio


class BatchProcessor:
    BATCH_SIZE = 25

    def __init__(self, df: pd.DataFrame, column_name: str, entities_instance: "Entities", batch_size: int = None, max_parallel_batches: int = 5):
        self.df = df
        self.column_name = column_name
        self.entities = entities_instance
        self.batch_size = batch_size or self.BATCH_SIZE
        self.max_parallel_batches = max_parallel_batches
        self.total_processed = 0
        self.total_dois = self._count_unique_dois()
        self.start_time = time.time()
        self._progress_lock = asyncio.Lock()  # Lock for updating progress safely

    def _count_unique_dois(self) -> int:
        return len(list(dict.fromkeys(self.df[self.column_name].dropna().tolist())))

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

    def _map_results(self, results: List[dict]) -> dict:
        return {
            r.get("doi", "").lower().replace("https://doi.org/", ""): r
            for r in results
        }

    async def process_batch(self, batch: List[str]) -> List[tuple[str, dict | None | str]]:
        batch_start = time.time()
        updated_batch = []

        try:
            results = await self.entities.get(batch)
            result_map = self._map_results(results)

            for doi in batch:
                doi_norm = Doi.normalize_doi(doi)
                result = result_map.get(doi_norm)

                if result is not None:
                    updated_batch.append((doi_norm, result))
                else:
                    updated_batch.append(await self.retry_single_doi(doi))

        except Exception as e:
            print(f"Batch failed: {e} — retrying DOIs individually...")
            updated_batch = await self._retry_entire_batch(batch)

        await self._update_progress(len(batch), batch_start)
        return updated_batch

    async def _retry_entire_batch(self, batch: List[str]) -> List[tuple[str, dict | None | str]]:
        return [await self.retry_single_doi(doi) for doi in batch]

    async def _update_progress(self, batch_size: int, batch_start: float):
        async with self._progress_lock:
            self.total_processed += batch_size
            elapsed = time.time() - self.start_time
            avg_time_per_doi = elapsed / self.total_processed if self.total_processed else 0
            remaining_dois = self.total_dois - self.total_processed
            eta_minutes = math.ceil(remaining_dois * avg_time_per_doi / 60)

            print(f"Finished batch: {self.total_processed}/{self.total_dois} DOIs processed "
                  f"(Batch time: {time.time() - batch_start:.1f}s, ETA: {eta_minutes} min)")

    async def run(self, update_fn):
        semaphore = asyncio.Semaphore(self.max_parallel_batches)

        async def run_batch_with_semaphore(batch):
            async with semaphore:
                await self._run_batch_with_retries(batch, update_fn)

        tasks = [
            run_batch_with_semaphore(batch)
            for batch in self.generate_batches()
        ]

        await asyncio.gather(*tasks)

    async def _run_batch_with_retries(self, batch: List[str], update_fn, max_retries: int = 3):
        success = False
        retries = 0

        while not success and retries < max_retries:
            batch_results = await self.process_batch(batch)

            if batch_results is not None:
                await self._update_dataframe(batch_results, update_fn)
                success = True
            else:
                retries += 1
                print(f"Retrying batch ({retries}/{max_retries})...")
                await asyncio.sleep(2 ** retries)

    async def _update_dataframe(self, batch_results: List[tuple[str, dict | None | str]], update_fn):
        for doi, result in batch_results:
            await update_fn(doi, result)
