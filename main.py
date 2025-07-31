import pandas as pd
from modules.entities import Works

radboud = "i145872427"
ror = "016xsfp80"
example_work = "W2125284466"
example_doi = "10.1111/ADB.12766"


def main():
    df = pd.read_excel("UKBsis Publication Details.xlsx")

    keys = ["cited_by_count", "referenced_works_count"]


    df = Works.enrich(df, keys)


    # Save the updated DataFrame
    df.to_excel("UKBsis_Publication_Details_Updated.xlsx", index=False)


if __name__ == "__main__":
    main()
