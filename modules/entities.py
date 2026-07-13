import asyncio
import json

import pandas as pd
from typing import Any, Coroutine
from modules.api import ApiClient, Session
from modules.utils import Doi, Filter, Keys
from modules.dataframe import DataFrameEnricher


class Entities:
    def __init__(self, entity_type: str, request=None):
        self.entity_type = entity_type
        self.request = request or ApiClient()
        self.filter_instance = Filter()

    async def get(self, input, keys = None):
        if isinstance(input, str):
            return await self._get_from_string(input, keys)
        elif isinstance(input, list):
            return await self._get_from_list(input, keys)
        else:
            raise ValueError("Unsupported input type for get()")

    async def _get_from_string(self, input, keys=None):
        identifier = Doi.check_identifier(input)
        if identifier == "doi":
            endpoint = Doi.build_endpoint(input)
        else:
            endpoint = f"{self.entity_type}/{Doi.normalize_id(input)}"
        if keys is not None:
            endpoint = self._with_select_keys(endpoint, keys)
        return await self.request.get_data(endpoint)

    async def _get_from_list(self, input_list, keys=None):
        if all(isinstance(i, tuple) for i in input_list):
            endpoint = f"{self.entity_type}{self.filter_instance.filter_attributes(input_list)}"
            if keys is not None:
                endpoint = self._with_select_keys(endpoint, keys)
            return await self.request.get_results_data(endpoint)
        elif all(isinstance(i, str) for i in input_list):
            identifier = Doi.check_identifier(input_list[0])
            endpoint = f"{self.entity_type}{Doi.batch_endpoint(input_list, identifier)}"
            if keys is not None:
                endpoint = self._with_select_keys(endpoint, keys)
            response = await self.request.get_data(endpoint)
            return response.get("results", []) if response else []
        else:
            raise ValueError("Unsupported input list type for get()")

    async def _get_from_batch(self, input_list, keys=None):
        identifier = Doi.check_identifier(input_list[0])
        if all(isinstance(i, str) for i in input_list):
            endpoint = f"{self.entity_type}{Doi.batch_endpoint(input_list, identifier)}"
            if keys is not None:
                endpoint = self._with_select_keys(endpoint, keys)
            sep = "&" if "?" in endpoint else "?"
            endpoint = f"{endpoint}{sep}per_page={self.request.per_page}"
            response = await self.request.get_data(endpoint)
            return response.get("results", []) if response else []
        else:
            raise ValueError("Unsupported input list type for get()")

    def _with_select_keys(self, endpoint: str, keys):
        root_keys = Keys.root_keys(keys)
        if self.entity_type == "works":
            if "doi" not in root_keys:
                root_keys = ["doi", *root_keys]
            if "id" not in root_keys:
                root_keys = ["id", *root_keys]
        return self.request.get_select(endpoint, root_keys) if root_keys else endpoint


class Works:
    def __init__(self, request=None):
        self.entities = Entities("works", request=request)
        self.entity_type = "works"

    def __getattr__(self, name):
        return getattr(self.entities, name)

    @staticmethod
    def get(input, keys: list[str] = None):
        async def _run():
            async with Session() as aio_session:
                request = ApiClient(session=aio_session)
                entities = Entities("works", request=request)
                return await entities.get(input, keys)
        return asyncio.run(_run())

    @staticmethod
    def enrich(
        df: pd.DataFrame,
        keys: list[str],
        column_name: str | None = None,
        batch_size: int | None = None,
        max_parallel_batches: int | None = None,
    ) -> pd.DataFrame | Coroutine[Any, Any, pd.DataFrame]:
        async def _run():
            nonlocal column_name
            if column_name is None:
                column_name = Doi.column_name(df)
            async with Session() as aio_session:
                request = ApiClient(session=aio_session)
                entities = Entities("works", request=request)
                enricher = DataFrameEnricher(df, keys, entities_instance=entities)
                await enricher.enrich(
                    keys=keys,
                    column_name=column_name,
                    batch_size=batch_size,
                    max_parallel_batches=max_parallel_batches,
                )
            return df
        return asyncio.run(_run())


if __name__ == "__main__":
    work = Works.get("W2125284466")
    print("\n".join(work.keys()))
    works = Works.get([("institutions.id", "i145872427"),("from_publication_date", "2026-04-01")])
    print(works)


