import pandas as pd
from modules.batcher import BatchProcessor
from modules.utils import Doi, Keys
from modules.runners import Runner
from modules.api import ApiClient


class DataFrameUpdater:
    def __init__(self, df: pd.DataFrame, keys: list[str], request: ApiClient, column_name: str = None):
        self.df = df
        self.keys = keys
        self.request = request
        self.column_name = column_name
        self.doi_series = df[column_name].astype(str).apply(Doi.normalize_id)
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
        for url, proj, key in to_fetch:
            extracted[key] = await self.request.resolve_api_url(url, proj, self.keys)

        self._assign(rows, extracted)

    def _match_rows(self, doi: str):
        doi_norm = Doi.normalize_id(doi)
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

    def _assign(self, rows, values: dict):
        if not values:
            return
        cols = list(values.keys())
        row_values = [[values.get(c) for c in cols]]
        data = pd.DataFrame(row_values, columns=cols)
        self.df.loc[rows, cols] = data.values.repeat(len(rows), axis=0)


class DataFrameEnricher:
    def __init__(self, df: pd.DataFrame, keys: list[str], entities_instance):
        self.df = df
        self.keys = keys
        self.updater = None
        self.entities = entities_instance

    async def enrich(self, column_name: str, keys, batch_size: int = None, max_parallel_batches: int = None):
        batch_size = batch_size or Runner.BATCH_SIZE
        max_parallel_batches = max_parallel_batches or Runner.MAX_PARALLEL_BATCHES

        self.updater = DataFrameUpdater(
            self.df,
            keys,
            request=self.entities.request,
            column_name=column_name
        )

        batcher = BatchProcessor(
            df=self.df,
            column_name=column_name,
            keys=keys,
            entities_instance=self.entities,
            batch_size=batch_size,
            max_parallel_batches=max_parallel_batches
        )

        await Runner.run_batches(batcher, self.updater.update)
