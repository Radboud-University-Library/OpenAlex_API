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
        out = {}
        for r in results or []:
            doi_url = r.get("doi") or (r.get("ids", {})).get("doi")
            if not doi_url:
                continue
            norm = Doi.normalize_doi(doi_url.replace("https://doi.org/", ""))
            out[norm] = r
        return out

    @staticmethod
    def column_name(df):
        candidates = ["doi", "DOI", "Doi", "DOI nummer", "Doi nummer"]
        for candidate in candidates:
            if candidate in df.columns:
                return candidate
        raise ValueError("No DOI column found in DataFrame. Please specify column_name.")

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

    @staticmethod
    def root_keys(keys) -> list[str]:
        if not keys:
            return []
        if isinstance(keys, str):
            keys = [k.strip() for k in keys.split(",") if k.strip()]

        roots: list[str] = []
        for k in keys:
            base, bracket_proj = Keys.split_keys(k)
            if base:
                roots.append(base.split(".", 1)[0])
            if bracket_proj:
                inner_root = bracket_proj.split(".", 1)[0]
                if inner_root in {"ids"}:
                    roots.append(inner_root)

        seen = set()
        return [r for r in roots if r and not (r in seen or seen.add(r))]

    def _extract_keys(obj, prefix=""):
        keys = []
        if isinstance(obj, dict):
            for k, v in obj.items():
                full_key = f"{prefix}.{k}" if prefix else k
                keys.append(full_key)
                keys.extend(Keys._extract_keys(v, prefix=full_key))
        elif isinstance(obj, list) and obj:
            keys.extend(Keys._extract_keys(obj[0], prefix=prefix + "[0]"))
        return keys

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
