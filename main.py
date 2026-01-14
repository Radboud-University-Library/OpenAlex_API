import pandas as pd
from modules.entities import Works
from modules.utils import List


radboud = "i145872427"
ror = "016xsfp80"
example_work = "W2125284466"
example_doi = "10.1111/ADB.12766"


def main():
    df = pd.read_excel("UKBsis Publication Details.xlsx")
    df = df.iloc[:1000]

    keys = [
            "fwci",
            "cited_by_count",
            "referenced_works_count",
            "referenced_works",
            "citation_normalized_percentile",
            "citation_normalized_percentile.value",
            "citation_normalized_percentile.is_in_top_1_percent",
            "citation_normalized_percentile.is_in_top_10_percent",
            "cited_by_percentile_year",
            "cited_by_percentile_year.min",
            "cited_by_percentile_year.max",
            "topics[display_name]",
            "topics[subfield.display_name]",
            "topics[domain.display_name]",
            "keywords[display_name]",
            "concepts",
            ]
    df = Works.enrich(df, keys)
    #df.to_excel("UKBsis_Publication_Details_Updated.xlsx", index=False)


    keys_2 = [
            "doi",
            "open_access.oa_status",
            "publication_date",
            "type",
            "primary_location[source.display_name]"
            "primary_location[source.host_organization_name]"
            "primary_location[source.host_organization_names]"
            ]

    df_referenced_works = List.flatten_list(df, "referenced_works")

    with pd.ExcelWriter("UKBsis_Publication_Details_Updated.xlsx") as writer:
        df.to_excel(writer, sheet_name="Publication Details", index=False)
        df_referenced_works.to_excel(writer, sheet_name="Referenced Works", index=False)

if __name__ == "__main__":
    main()

