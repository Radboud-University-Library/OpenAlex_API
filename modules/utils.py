import json
from typing import List


class Json:
    @staticmethod
    def export_to_json(data, file_path):
        """ Export Json data """
        with open(file_path, "w") as file:
            json.dump(data, file, indent=4)

    @staticmethod
    def filter_json(json_data, keys_to_extract):
        """ Create list of based on selection of keys from a dict """
        if isinstance(json_data, dict):
            json_data = [json_data]

        json_selection = [
            {key: item[key] for key in keys_to_extract if key in item}
            for item in json_data
        ]

        return json_selection[0] if len(json_selection) == 1 else json_selection


class Doi:
    @staticmethod
    def normalize_doi(doi):
        if not isinstance(doi, str) or not doi.strip():
            raise ValueError("DOI must be a non-empty string.")
        return doi.strip().lower().rstrip('.')

    @staticmethod
    def build_endpoint(doi):
        doi = Doi.normalize_doi(doi)
        return f"works/https://doi.org/{doi}"

    @staticmethod
    def batch_endpoint(dois: List[str]) -> str:
        doi_filter = "|".join([doi.strip() for doi in dois])
        return f"?filter=doi:{doi_filter}"
