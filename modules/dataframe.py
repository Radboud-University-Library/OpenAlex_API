import pandas as pd
from modules.batcher import BatchProcessor
from modules.utils import Doi, Keys
from modules.runners import Runner
from modules.api import ApiRequest


class DataFrameUpdater:
    def __init__(self, df: pd.DataFrame, keys: list[str], request: ApiRequest):
        self.df = df
        self.keys = keys
        self.request = request
        self.doi_series = df["DOI"].astype(str).apply(Doi.normalize_doi)
        self.url_cache = {}

        for key in self.keys:
            if key not in self.df.columns:
                self.df[key] = None

    async def update(self, doi: str, result: dict | None | str):
        doi_norm = Doi.normalize_doi(doi)
        matching_rows = self.df[self.doi_series == doi_norm]

        if matching_rows.empty:
            print(f"No match for DOI: {doi}")
            return

        if isinstance(result, str) and result == "404 error":
            self._fill_all_keys(matching_rows.index, "URL not found")
            return

        for key in self.keys:
            value = await self._extract_value(result, key)
            if isinstance(value, (dict, list)):
                value = str(value)
            self.df.loc[matching_rows.index, key] = value

    def _fill_all_keys(self, index, value):
        for key in self.keys:
            self.df.loc[index, key] = value

    async def _extract_value(self, data: dict, key: str):
        if not isinstance(data, dict):
            return data

        raw_value = Keys.get_nested(data, key)

        if isinstance(raw_value, str) and raw_value.startswith("https://api.openalex.org/"):
            if raw_value in self.url_cache:
                return self.url_cache[raw_value]
            print(f"Key: {key} returns URL: {raw_value}. API request returns data.")
            data = await self.request.get_url(raw_value)
            self.url_cache[raw_value] = data
            return data

        if isinstance(raw_value, (dict, list)):
            return raw_value

        return raw_value


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
