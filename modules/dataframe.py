import pandas as pd
import asyncio
from modules.batcher import BatchProcessor
from modules.utils import Doi, Keys, Excel
from modules.runners import Runner
from modules.api import ApiClient


class DataFrameUpdater:
    def __init__(self, df: pd.DataFrame, keys: list[str], request: ApiClient):
        self.df = df
        self.keys = keys
        self.request = request
        self.doi_series = df["DOI"].astype(str).apply(Doi.normalize_doi)
        self.url_cache: dict[str, dict | list | None] = {}

        for key in self.keys:
            if key not in self.df.columns:
                self.df[key] = None

    async def update(self, doi: str, result: dict | None | str):
        rows = self._match_rows(doi)
        if rows is None:
            return

        if self._is_404(result):
            self._fill_all_keys(rows, "URL not found")
            return

        extracted, to_fetch = self._prepare_extractions(result)
        await self._fetch_urls_in_order(to_fetch)
        self._resolve_pending_extractions(extracted, result, to_fetch)

        coerced = {k: Excel.coerce_for_excel(v) for k, v in extracted.items()}
        self._assign(rows, coerced)

    def _match_rows(self, doi: str):
        doi_norm = Doi.normalize_doi(doi)
        rows = self.df.index[self.doi_series == doi_norm]
        if len(rows) == 0:
            print(f"No match for DOI: {doi}")
            return None
        return rows

    @staticmethod
    def _is_404(result) -> bool:
        return isinstance(result, str) and result == "404 error"

    def _fill_all_keys(self, rows, value):
        for key in self.keys:
            self.df.loc[rows, key] = value

    def _prepare_extractions(self, result: dict | None | str):

        extracted: dict[str, object] = {}
        to_fetch: list[tuple[str, str | None, str]] = []

        for key in self.keys:
            base, proj = Keys.split_keys(key)
            raw = Keys.get_nested_keys(result, base) if isinstance(result, dict) else result

            if isinstance(raw, str) and raw.startswith("https://api.openalex.org/"):
                extracted[key] = None
                to_fetch.append((raw, proj, key))
            else:
                extracted[key] = Keys.project_keys(raw, proj)

        return extracted, to_fetch

    async def _fetch_urls_in_order(self, to_fetch):
        unique_ordered, seen = [], set()
        for url, _, _ in to_fetch:
            if url not in self.url_cache and url not in seen:
                unique_ordered.append(url); seen.add(url)
        if not unique_ordered:
            return
        tasks = [asyncio.create_task(self.request.get_url(u)) for u in unique_ordered]
        for u, t in zip(unique_ordered, asyncio.as_completed(tasks)):
            data = await t
            self.url_cache[u] = data

    def _resolve_pending_extractions(self, extracted: dict, result: dict | None | str,
                                     to_fetch: list[tuple[str, str | None, str]]):
        for url, proj, key in to_fetch:
            data = self.url_cache.get(url)
            extracted[key] = Keys.project_keys(data, proj)

    def _assign(self, rows, values: dict):
        for key, val in values.items():
            self.df.loc[rows, key] = val


class DataFrameEnricher:
    def __init__(self, df: pd.DataFrame, keys: list[str], entities_instance):
        self.df = df
        self.updater = DataFrameUpdater(df, keys, request=entities_instance.request)
        self.entities = entities_instance

    async def enrich(self, column_name: str, batch_size: int = None, max_parallel_batches: int = None):
        batch_size = batch_size or Runner.BATCH_SIZE
        max_parallel_batches = max_parallel_batches or Runner.MAX_PARALLEL_BATCHES

        batcher = BatchProcessor(
            df=self.df,
            column_name=column_name,
            entities_instance=self.entities,
            batch_size=batch_size,
            max_parallel_batches=max_parallel_batches
        )

        await Runner.run_batches(batcher, self.updater.update)
