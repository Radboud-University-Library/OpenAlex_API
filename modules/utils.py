import re
from typing import List


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

    @staticmethod
    def unique_normalized_dois(dois: list[str]) -> list[str]:
        seen = set()
        out = []
        for d in dois:
            if not isinstance(d, str) or not d.strip():
                continue
            norm = Doi.normalize_doi(d)
            if norm not in seen:
                seen.add(norm)
                out.append(norm)
        return out

    @staticmethod
    def map_results_by_doi(results: list[dict]) -> dict[str, dict]:
        return {
            Doi.normalize_doi(r.get("doi", "")): r
            for r in results if "doi" in r
        }

class Filter:
    @staticmethod
    def filter_attributes(filters: list[tuple[str, str]]) -> str:
        if not isinstance(filters, (list, tuple)):
            raise ValueError("Filters must be a list or tuple of key-value pairs")

        filter_strings = [f"{attribute}:{value}" for attribute, value in filters]
        filter_endpoint = "?filter=" + ",".join(filter_strings)
        return filter_endpoint


class Keys:
    @staticmethod
    def get_nested_keys(data, key_path):
        try:
            parts = key_path.replace("[", ".").replace("]", "").split(".")
            for part in parts:
                if isinstance(data, list):
                    part = int(part)
                    data = data[part]
                elif isinstance(data, dict):
                    data = data.get(part)
                else:
                    return None
            return data
        except (TypeError, KeyError, IndexError, ValueError, AttributeError):
            return None

    @staticmethod
    def split_keys(key: str) -> tuple[str, str | None]:
        m = re.match(r'^(.*?)\[(.+)\]$', key)
        return (m.group(1), m.group(2)) if m else (key, None)

    @staticmethod
    def project_keys(data, projection: str | None):
        if projection is None:
            return data
        if isinstance(data, dict) and "results" in data:
            data = data["results"]
        if isinstance(data, list):
            out = []
            for item in data:
                v = Keys.get_nested_keys(item, projection)
                out.append(Url.remove_url(v))
            return out
        if isinstance(data, dict):
            v = Keys.get_nested_keys(data, projection)
            return Url.remove_url(v)
        return None

class Url:
    @staticmethod
    def remove_url(value):
        if isinstance(value, str) and value.startswith("https://openalex.org/"):
            return value.replace("https://openalex.org/", "")
        return value

class Excel:
    @staticmethod
    def coerce_for_excel(value):
        if isinstance(value, (dict, list)):
            return str(value)
        return value
