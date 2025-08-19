import asyncio
import pandas as pd
from modules.api import ApiRequest, Session
from modules.utils import Doi, Filter
from modules.dataframe import DataFrameEnricher


class Entities:
    def __init__(self, entity_type: str, request=None):
        self.entity_type = entity_type
        self.request = request or ApiRequest()
        self.filter_instance = Filter()

    async def get(self, input):
        if isinstance(input, str):
            return await self._get_from_string(input)
        elif isinstance(input, list):
            return await self._get_from_list(input)
        else:
            raise ValueError("Unsupported input type for get()")

    async def _get_from_string(self, input):
        if input.lower().startswith("10."):
            endpoint = Doi.build_endpoint(input)
        else:
            endpoint = f"{self.entity_type}/{input}"
        return await self.request.get_data(endpoint)

    async def _get_from_list(self, input_list):
        if all(isinstance(i, tuple) for i in input_list):
            endpoint = f"{self.entity_type}{self.filter_instance.filter_attributes(input_list)}"
            print(endpoint)
            return await self.request.get_results_data(endpoint)
        elif all(isinstance(i, str) for i in input_list):
            endpoint = f"{self.entity_type}{Doi.batch_endpoint(input_list)}"
            response = await self.request.get_data(endpoint)
            return response.get("results", []) if response else []
        else:
            raise ValueError("Unsupported input list type for get()")


class Works:
    def __init__(self, request=None):
        self.entities = Entities("works", request=request)
        self.entity_type = "works"

    def __getattr__(self, name):
        return getattr(self.entities, name)

    @staticmethod
    def get(input):
        async def _run():
            async with Session() as aio_session:
                request = ApiRequest(session=aio_session)
                entities = Entities("works", request=request)
                return await entities.get(input)
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
            request = ApiRequest(session=aio_session)
            entities = Entities("works", request=request)
            enricher = DataFrameEnricher(df, keys, entities_instance=entities)
            await enricher.enrich(column_name=column_name)

    @staticmethod
    def keys(sample_id="W2125284466") -> list[str]:
        """Returns all available (flattened) metadata keys from a sample work object."""
        def extract_keys(obj, prefix=""):
            keys = []
            if isinstance(obj, dict):
                for k, v in obj.items():
                    full_key = f"{prefix}.{k}" if prefix else k
                    keys.append(full_key)
                    keys.extend(extract_keys(v, prefix=full_key))
            elif isinstance(obj, list) and obj:
                keys.extend(extract_keys(obj[0], prefix=prefix + "[0]"))
            return keys

        async def _get_keys():
            async with Session() as aio_session:
                request = ApiRequest(session=aio_session)
                work = await request.get_data(f"works/{sample_id}")
                return extract_keys(work) if work else []

        return asyncio.run(_get_keys())


if __name__ == "__main__":
    work = Works.get("W2125284466")
    works = Works.get([("institutions.id", "i145872427"),("from_publication_date", "2025-08-01")])
    print(works)
    print(work.keys())
    #print(json.dumps(work["cited_by_percentile_year"], indent=2))
