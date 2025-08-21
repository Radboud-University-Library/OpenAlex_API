import pandas as pd
from modules.batcher import BatchProcessor
from modules.utils import Doi, Keys, Url
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
        """Supports bracket syntax like 'cited_by_api_url[ids.openalex]'.
           - Left of [ ]: the base field to read from the work (may be a URL)
           - Inside [ ]: nested field to extract from the fetched result (applied to each item)
        """
        if not isinstance(data, dict):
            return data
        base_key, nested_key = self._split_bracket_key(key)
        raw_value = Keys.get_nested_keys(data, base_key)
        if isinstance(raw_value, str) and raw_value.startswith("https://api.openalex.org/"):
            if raw_value in self.url_cache:
                fetched = self.url_cache[raw_value]
            else:
                print(f"Key: {base_key} returns URL: {raw_value}. Fetching…")
                fetched = await self.request.get_url(raw_value)
                self.url_cache[raw_value] = fetched
            if nested_key:
                return self._extract_from_list(fetched, nested_key)
            return fetched
        if isinstance(raw_value, (dict, list)):
            return raw_value
        return raw_value

    def _split_bracket_key(self, key: str) -> tuple[str, str | None]:
        """Split 'field[sub.field]' into ('field', 'sub.field'). If no brackets, returns (key, None)."""
        if "[" in key and key.endswith("]"):
            base, rest = key.split("[", 1)
            nested = rest[:-1]  # strip trailing ']'
            return base, nested
        return key, None

    def _extract_from_list(self, data, nested_key: str):
        """Extract nested_key from each item in a list response. Supports dot-paths via Keys.get_nested.
           Special-case: if nested_key == 'ids.openalex' (or resolves to that), return compact IDs.
        """
        if not isinstance(data, list):
            if isinstance(data, dict) and "results" in data:
                data = data["results"]
            else:
                return None
        out = []
        for item in data:
            value = Keys.get_nested_keys(item, nested_key)
            value = Url.remove_url(value)
            out.append(value)
        return out


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
