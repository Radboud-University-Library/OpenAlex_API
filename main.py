import json

import pandas as pd
from modules.entities import Works
from modules.utils import Excel


radboud = "i145872427"
ror = "016xsfp80"
example_work = "W2125284466"
example_doi = "10.1111/ADB.12766"


def main():
    # Choose either "excel" or "json".
    output_format = "json"

    df = pd.read_excel("surf_publication_details.xlsx")
    #df = df.iloc[:5000]

    keys = [
            "authorships",

            "countries_distinct_count",
            "institutions_distinct_count",
            "corresponding_author_ids",
            "corresponding_institution_ids",
            "apc_list",
            "apc_paid",
            "fwci",
            "cited_by_count",
            "citation_normalized_percentile",
            #"citation_normalized_percentile.value",
            #"citation_normalized_percentile.is_in_top_1_percent",
            #"citation_normalized_percentile.is_in_top_10_percent",
            "cited_by_percentile_year",
            #"cited_by_percentile_year.min",
            #"cited_by_percentile_year.max",
            "primary_topic",
            "topics",
            #"topics[display_name]",
            #"topics[subfield.display_name]",
            #"topics[domain.display_name]",
            "keywords",
            #"keywords[display_name]",
            "concepts",
            "sustainable_development_goals",
            "awards",
            "funders",
            "referenced_works_count",
            "referenced_works",
            "counts_by_year"
            ]
    df = Works.enrich(df, keys)
    #df.to_excel("surf_publication_details_updated.xlsx", index=False)

    export_results(df, output_format)


def export_results(df, output_format):
    output_format = output_format.lower()

    if output_format == "excel":
        _prepare_for_excel(df).to_excel(
            "surf_publication_details_updated_.xlsx",
            sheet_name="Publication Details",
            index=False,
        )
        return

    if output_format == "json":
        data = json.loads(df.to_json(orient="records", date_format="iso"))
        with open("surf_publication_details_updated_.json", "w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=2)
        return

    raise ValueError('output_format must be either "excel" or "json"')


def _prepare_for_excel(df):
    return df.apply(lambda column: column.map(Excel.coerce_for_excel))


if __name__ == "__main__":
    main()

