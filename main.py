import pandas as pd
import asyncio
from modules.api import ApiRequest, Session, Entities
from modules.utils import Doi
from modules.batching import BatchProcessor


radboud = "i145872427"
ror = "016xsfp80"
example_work = "W2125284466"
example_doi = "10.1111/ADB.12766"


if __name__ == "__main__":


    df = pd.read_excel("UKBsis Publication Details.xlsx")


    # Initialize new columns
    df["cited_by_count"] = None
    df["referenced_works_count"] = None


    # Define update_fn
    async def update_fn(df: pd.DataFrame, doi: str, result: dict | None | str):
        doi_normalized = doi.strip().lower()

        # Add normalized column (do this only once if not already present)
        if "DOI_normalized" not in df.columns:
            df["DOI_normalized"] = df["DOI"].astype(str).apply(Doi.normalize_doi)

        matching_rows = df[df["DOI_normalized"] == doi_normalized]

        if matching_rows.empty:
            print(f"No match found in DataFrame for DOI: {doi}")
            return

        elif result == "404 error":
            df.loc[matching_rows.index, "cited_by_count"] = "URL not found"
            df.loc[matching_rows.index, "referenced_works_count"] = "URL not found"

        else:
            # Valid result, update cited_by_count and referenced_works_count
            df.loc[matching_rows.index, "cited_by_count"] = result.get("cited_by_count")
            df.loc[matching_rows.index, "referenced_works_count"] = result.get("referenced_works_count")


    # Main async runner
    async def enrich_with_batches(df: pd.DataFrame):
        async with Session() as aio_session:
            request = ApiRequest(session=aio_session)
            entities = Entities("works", request=request)

            batcher = BatchProcessor(df=df, column_name="DOI", entities_instance=entities)
            await batcher.run(update_fn=update_fn)


    # Run
    asyncio.run(enrich_with_batches(df))

    # Save the updated DataFrame
    df.to_excel("UKBsis_Publication_Details_Updated.xlsx", index=False)