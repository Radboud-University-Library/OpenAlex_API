import pandas as pd
import asyncio
from modules.dataframe import DataFrameEnricher


radboud = "i145872427"
ror = "016xsfp80"
example_work = "W2125284466"
example_doi = "10.1111/ADB.12766"


async def main():
    df = pd.read_excel("UKBsis Publication Details.xlsx")

    keys = ["cited_by_count", "referenced_works_count"]


    enricher = DataFrameEnricher(df, keys)
    await enricher.enrich(entity_type="works", column_name="DOI")

    # Save the updated DataFrame
    df.to_excel("UKBsis_Publication_Details_Updated.xlsx", index=False)


if __name__ == "__main__":
    asyncio.run(main())
