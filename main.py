import pandas as pd
from modules.entities import Works
from modules.utils import List


radboud = "i145872427"
ror = "016xsfp80"
example_work = "W2125284466"
example_doi = "10.1111/ADB.12766"


def main():
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

    df_referenced_works = List.flatten_list(df, "referenced_works", keep_urls=True)
    #df_referenced_works = Works.enrich(df_referenced_works, keys_2, column_name="id")

    with pd.ExcelWriter("surf_publication_details_updated_.xlsx") as writer:
        df.to_excel(writer, sheet_name="Publication Details", index=False)
        df_referenced_works.to_excel(writer, sheet_name="Referenced Works", index=False)

if __name__ == "__main__":
    main()

