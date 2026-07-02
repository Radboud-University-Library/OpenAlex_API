import re
from typing import List
from collections import Counter
import pandas as pd
import ast


class Doi:
    @staticmethod
    def normalize_id(id):
        if not isinstance(id, str) or not id.strip():
            raise ValueError("DOI must be a non-empty string.")
        raw = id.strip().rstrip(".")

        openalex_id = Doi._extract_openalex_id(raw)
        if openalex_id:
            return openalex_id

        doi = Doi._extract_doi(raw)
        if doi:
            return doi.lower()

        return raw.lower()

    @staticmethod
    def _extract_openalex_id(value: str) -> str | None:
        v = value.strip()
        lower = v.lower()
        for prefix in ("https://openalex.org/", "http://openalex.org/",
                       "https://api.openalex.org/", "http://api.openalex.org/"):
            if lower.startswith(prefix):
                v = v[len(prefix):]
                lower = v.lower()
                break

        if lower.startswith("works/"):
            v = v.split("/", 1)[1]
            lower = v.lower()

        if re.match(r"^[Ww]\d+$", v):
            return f"W{v[1:]}"
        return None

    @staticmethod
    def _extract_doi(value: str) -> str | None:
        v = value.strip()
        lower = v.lower()
        if lower.startswith("https://doi.org/"):
            v = v.split("doi.org/", 1)[1]
            lower = v.lower()
        elif lower.startswith("http://doi.org/"):
            v = v.split("doi.org/", 1)[1]
            lower = v.lower()
        if lower.startswith("10."):
            return v
        return None

    @staticmethod
    def build_endpoint(doi):
        doi = Doi.normalize_id(doi)
        return f"works/https://doi.org/{doi}"

    @staticmethod
    def batch_endpoint(dois: List[str], identifier) -> str:
        normalized = [Doi.normalize_id(doi) for doi in dois]
        doi_filter = "|".join(normalized)
        return f"?filter={identifier}:{doi_filter}"

    @staticmethod
    def unique_normalized_dois(dois: list[str]) -> list[str]:
        seen = set()
        out = []
        for d in dois:
            if not isinstance(d, str) or not d.strip():
                continue
            norm = Doi.normalize_id(d)
            if norm not in seen:
                seen.add(norm)
                out.append(norm)
        return out

    @staticmethod
    def map_results_by_doi(results: list[dict]) -> dict[str, dict]:
        return Doi.map_results_by_id(results, identifier="doi")

    @staticmethod
    def map_results_by_id(results: list[dict], identifier: str) -> dict[str, dict]:
        out = {}
        for r in results or []:
            if identifier == "openalex_id":
                raw = r.get("id") or (r.get("ids", {})).get("openalex")
            else:
                raw = r.get("doi") or (r.get("ids", {})).get("doi")
            if not raw:
                continue
            norm = Doi.normalize_id(raw)
            out[norm] = r
        return out

    @staticmethod
    def column_name(df):
        candidates = ["doi", "DOI", "Doi", "DOI nummer", "Doi nummer"]
        for candidate in candidates:
            if candidate in df.columns:
                return candidate
        raise ValueError("No DOI column found in DataFrame. Please specify column_name.")

    @staticmethod
    def check_identifier(item):
        if not isinstance(item, str) or not item.strip():
            raise ValueError("Identifier must be a non-empty string.")

        if Doi._extract_openalex_id(item):
            return "openalex_id"
        if Doi._extract_doi(item):
            return "doi"

        raise ValueError(f"Unknown identifier format: {item}")

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


class List:
    @staticmethod
    def flatten_list(df, column, keep_urls: bool = False):
        all_items = []
        for val in df[column].dropna():
            if isinstance(val, str):
                val = val.strip()
                if val.startswith("[") and val.endswith("]"):
                    try:
                        val = ast.literal_eval(val)
                        if not isinstance(val, list):
                            continue
                    except Exception as e:
                        print(f"Skipping row due to error: {e}")
                        continue
                else:
                    continue

            if isinstance(val, list):
                all_items.extend(val)

        if keep_urls:
            all_items = [item for item in all_items if isinstance(item, str)]
        else:
            all_items = [
                item.replace("https://openalex.org/", "")
                for item in all_items if isinstance(item, str)
            ]
        item_counts = Counter(all_items)
        return pd.DataFrame(item_counts.items(), columns=["id", "count"])\
                 .sort_values(by="count", ascending=False)

class Excel:
    @staticmethod
    def coerce_for_excel(value):
        if isinstance(value, (dict, list)):
            return str(value)
        return value

