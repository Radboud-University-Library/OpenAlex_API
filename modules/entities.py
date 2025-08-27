import asyncio
import pandas as pd
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
        endpoint = Doi.build_endpoint(input) if input.lower().startswith("10.") else f"{self.entity_type}/{input}"
        endpoint = self._with_select_keys(endpoint, keys)
        return await self.request.get_data(endpoint)

    async def _get_from_list(self, input_list, keys=None):
        if all(isinstance(i, tuple) for i in input_list):
            endpoint = f"{self.entity_type}{self.filter_instance.filter_attributes(input_list)}"
            endpoint = self._with_select_keys(endpoint, keys)
            return await self.request.get_results_data(endpoint)
        elif all(isinstance(i, str) for i in input_list):
            endpoint = f"{self.entity_type}{Doi.batch_endpoint(input_list)}"
            endpoint = self._with_select_keys(endpoint, keys)
            response = await self.request.get_data(endpoint)
            return response.get("results", []) if response else []
        else:
            raise ValueError("Unsupported input list type for get()")

    def _with_select_keys(self, endpoint: str, keys):
        root_keys = Keys.root_keys(keys)
        select_keys = Entities._extract_root_keys(root_keys)
        return self.request.get_select(endpoint, select_keys) if select_keys else endpoint

    @staticmethod
    def _extract_root_keys(keys):
        return Keys.root_keys(keys)

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
    def enrich(df: pd.DataFrame, keys: list[str], column_name: str = None):
        if column_name is None:
            for candidate in ["doi", "DOI", "Doi"]:
                if candidate in df.columns:
                    column_name = candidate
                    break
            if column_name is None:
                raise ValueError("No DOI column found in DataFrame. Please specify column_name.")
        asyncio.run(Works._enrich_async(df, keys, column_name))
        return df

    @staticmethod
    async def _enrich_async(df: pd.DataFrame, keys: list[str], column_name: str):
        async with Session() as aio_session:
            request = ApiClient(session=aio_session)
            entities = Entities("works", request=request)
            enricher = DataFrameEnricher(df, keys, entities_instance=entities)
            await enricher.enrich(column_name=column_name, keys=keys)




if __name__ == "__main__":
    work = Works.get("W2125284466",["id"])
    works = Works.get([("institutions.id", "i145872427"),("from_publication_date", "2025-08-01")],["id"])
    print(works)
    #print("\n".join(work.keys()))
    #print(json.dumps(work["cited_by_percentile_year"], indent=2))
