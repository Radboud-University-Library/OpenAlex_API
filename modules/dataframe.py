import pandas as pd
from modules.api import ApiRequest, Entities, Session
from modules.batcher import BatchProcessor
from modules.utils import Doi
from modules.runners import Runner



class DataFrameUpdater:
    def __init__(self, df: pd.DataFrame, keys: list[str]):
        self.df = df
        self.keys = keys
        self.doi_series = df["DOI"].astype(str).apply(Doi.normalize_doi)

    async def update(self, doi: str, result: dict | None | str):
        doi_norm = Doi.normalize_doi(doi)
        matching_rows = self.df[self.doi_series == doi_norm]

        if matching_rows.empty:
            print(f"No match for DOI: {doi}")
            return

        for key in self.keys:
            if key not in self.df.columns:
                self.df[key] = None

        value = "URL not found" if result == "404 error" else result
        for key in self.keys:
            self.df.loc[matching_rows.index, key] = value.get(key) if isinstance(value, dict) else value


class DataFrameEnricher:
    def __init__(self, df: pd.DataFrame, keys: list[str]):
        self.df = df
        self.updater = DataFrameUpdater(df, keys)

    async def enrich(self, entity_type: str, column_name: str, batch_size: int = None, max_parallel_batches: int = None):
        batch_size = batch_size or Runner.BATCH_SIZE
        max_parallel_batches = max_parallel_batches or Runner.MAX_PARALLEL_BATCHES

        async with Session() as aio_session:
            request = ApiRequest(session=aio_session)
            entities = Entities(entity_type, request=request)

            batcher = BatchProcessor(
                df=self.df,
                column_name=column_name,
                entities_instance=entities,
                batch_size=batch_size,
                max_parallel_batches=max_parallel_batches
            )

            await Runner.run_batches(batcher, self.updater.update)
