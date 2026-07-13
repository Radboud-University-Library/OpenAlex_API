import ast
import json
from pathlib import Path

import pandas as pd

from modules.entities import Works
from modules.utils import Doi


CACHE_VERSION = 1
REFRESH_REMAINING_KEY = "refresh_remaining"
FOLLOWUP_ITEMS_CACHE_KEY = "followup_items"
FOLLOWUP_METADATA_CACHE_KEY = "followup_metadata"


def add_followup_items(
    df: pd.DataFrame,
    source_field: str,
    column_name: str | None = None,
    cache_path: str | Path | None = None,
    refresh: bool = False,
    checkpoint_size: int = 5000,
    batch_size: int | None = None,
    max_parallel_batches: int | None = None,
) -> pd.DataFrame:
    """Add a nested OpenAlex list field used for follow-up requests."""
    if not source_field:
        raise ValueError("source_field must be provided")
    if checkpoint_size <= 0:
        raise ValueError("checkpoint_size must be greater than zero")

    column_name = column_name or Doi.column_name(df)
    normalized_ids = df[column_name].apply(_normalize_or_none)
    unique_ids = list(dict.fromkeys(identifier for identifier in normalized_ids if identifier))
    cache_path = Path(cache_path or f"{_safe_filename(source_field)}_followup_cache.json")
    cache = _load_items_cache(cache_path)
    cached_values = cache[FOLLOWUP_ITEMS_CACHE_KEY]

    if refresh:
        pending_ids = cache.get(REFRESH_REMAINING_KEY)
        if pending_ids is None:
            pending_ids = unique_ids
            cache[REFRESH_REMAINING_KEY] = pending_ids
            _save_cache(cache_path, cache)
    else:
        pending_ids = [
            identifier for identifier in unique_ids if identifier not in cached_values
        ]

    if pending_ids:
        print(
            f"Fetching {source_field} for {len(pending_ids)} of "
            f"{len(unique_ids)} unique works."
        )
        for start in range(0, len(pending_ids), checkpoint_size):
            identifiers = pending_ids[start : start + checkpoint_size]
            pending = pd.DataFrame({column_name: identifiers})
            enriched = Works.enrich(
                pending,
                [source_field],
                column_name=column_name,
                batch_size=batch_size,
                max_parallel_batches=max_parallel_batches,
            )
            _update_items_cache(cached_values, enriched, column_name, source_field)
            if refresh:
                remaining = pending_ids[start + len(identifiers) :]
                if remaining:
                    cache[REFRESH_REMAINING_KEY] = remaining
                else:
                    cache.pop(REFRESH_REMAINING_KEY, None)
            _save_cache(cache_path, cache)
    else:
        print(f"Reusing {source_field} for all {len(unique_ids)} works from cache.")

    df[source_field] = normalized_ids.map(cached_values)
    return df


def enrich_followup_occurrences(
    df: pd.DataFrame,
    source_field: str,
    keys: list[str],
    citing_column: str | None = None,
    metadata_cache_path: str | Path | None = None,
    checkpoint_size: int = 5000,
    batch_size: int | None = None,
    max_parallel_batches: int | None = None,
) -> pd.DataFrame:
    """Return one enriched row per follow-up item occurrence."""
    if not source_field:
        raise ValueError("source_field must be provided")
    if source_field not in df.columns:
        raise ValueError(f"The DataFrame does not contain a {source_field} column")
    if not keys:
        raise ValueError("At least one follow-up key must be provided")
    if checkpoint_size <= 0:
        raise ValueError("checkpoint_size must be greater than zero")

    citing_column = citing_column or Doi.column_name(df)
    occurrences = []
    for citing_work, followup_items in zip(df[citing_column], df[source_field]):
        for followup_item in _as_item_list(followup_items):
            followup_item_id = _normalize_or_none(followup_item)
            if not followup_item_id:
                continue
            occurrences.append(
                {
                    "citing_work_id": citing_work,
                    "followup_source_field": source_field,
                    "followup_item_id": followup_item_id,
                }
            )

    occurrence_df = pd.DataFrame(
        occurrences,
        columns=["citing_work_id", "followup_source_field", "followup_item_id"],
    )
    if occurrence_df.empty:
        for key in keys:
            occurrence_df[key] = None
        return occurrence_df

    # Fetch each follow-up item once, then merge back to all occurrences.
    unique_items = occurrence_df["followup_item_id"].drop_duplicates().tolist()
    metadata_cache_path = Path(
        metadata_cache_path
        or f"{_safe_filename(source_field)}_followup_metadata_cache.json"
    )
    metadata_cache = _load_metadata_cache(metadata_cache_path)
    metadata = metadata_cache[FOLLOWUP_METADATA_CACHE_KEY]
    pending_items = [
        followup_item_id
        for followup_item_id in unique_items
        if _metadata_missing_keys(metadata.get(followup_item_id), keys)
    ]

    if pending_items:
        print(
            f"Fetching metadata for {len(pending_items)} of "
            f"{len(unique_items)} unique follow-up items."
        )
        for start in range(0, len(pending_items), checkpoint_size):
            identifiers = pending_items[start : start + checkpoint_size]
            pending = pd.DataFrame({"followup_item_id": identifiers})
            enriched = Works.enrich(
                pending,
                keys,
                column_name="followup_item_id",
                batch_size=batch_size,
                max_parallel_batches=max_parallel_batches,
            )
            _update_metadata_cache(metadata, enriched, keys)
            _save_cache(metadata_cache_path, metadata_cache)
    else:
        print(
            f"Reusing metadata for all {len(unique_items)} "
            "unique follow-up items from cache."
        )

    details = _metadata_to_dataframe(unique_items, metadata, keys)
    return occurrence_df.merge(
        details,
        on="followup_item_id",
        how="left",
        sort=False,
        validate="many_to_one",
    )


def _as_item_list(value):
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str)]
    if isinstance(value, str) and value.strip().startswith("["):
        try:
            parsed = ast.literal_eval(value)
        except (SyntaxError, ValueError):
            return []
        if isinstance(parsed, list):
            return [item for item in parsed if isinstance(item, str)]
    return []


def _normalize_or_none(value):
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return Doi.normalize_id(value)
    except ValueError:
        return None


def _safe_filename(value):
    return "".join(character if character.isalnum() else "_" for character in value)


def _load_items_cache(cache_path):
    temporary_path = cache_path.with_suffix(cache_path.suffix + ".tmp")
    candidates = [path for path in (cache_path, temporary_path) if path.exists()]
    if not candidates:
        return {"version": CACHE_VERSION, FOLLOWUP_ITEMS_CACHE_KEY: {}}

    candidates.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    last_error = None
    for candidate in candidates:
        try:
            cache = json.loads(candidate.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            last_error = exc
            continue

        if (
            cache.get("version") == CACHE_VERSION
            and isinstance(cache.get(FOLLOWUP_ITEMS_CACHE_KEY), dict)
        ):
            if candidate == temporary_path:
                print("Recovering from the newer follow-up item checkpoint.")
            return cache

    raise ValueError(f"Could not read follow-up item cache: {cache_path}") from last_error


def _load_metadata_cache(cache_path):
    temporary_path = cache_path.with_suffix(cache_path.suffix + ".tmp")
    candidates = [path for path in (cache_path, temporary_path) if path.exists()]
    if not candidates:
        return {"version": CACHE_VERSION, FOLLOWUP_METADATA_CACHE_KEY: {}}

    candidates.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    last_error = None
    for candidate in candidates:
        try:
            cache = json.loads(candidate.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            last_error = exc
            continue

        if (
            cache.get("version") == CACHE_VERSION
            and isinstance(cache.get(FOLLOWUP_METADATA_CACHE_KEY), dict)
        ):
            if candidate == temporary_path:
                print("Recovering from the newer follow-up metadata checkpoint.")
            return cache

    raise ValueError(
        f"Could not read follow-up metadata cache: {cache_path}"
    ) from last_error


def _update_items_cache(cached_values, enriched, column_name, source_field):
    records = json.loads(enriched.to_json(orient="records", date_format="iso"))
    for row in records:
        identifier = _normalize_or_none(row.get(column_name))
        if identifier:
            cached_values[identifier] = row.get(source_field)


def _metadata_missing_keys(record, keys):
    return not isinstance(record, dict) or any(key not in record for key in keys)


def _update_metadata_cache(metadata, enriched, keys):
    records = json.loads(enriched.to_json(orient="records", date_format="iso"))
    for row in records:
        identifier = _normalize_or_none(row.get("followup_item_id"))
        if not identifier:
            continue
        record = metadata.setdefault(identifier, {})
        for key in keys:
            record[key] = row.get(key)


def _metadata_to_dataframe(followup_item_ids, metadata, keys):
    rows = []
    for followup_item_id in followup_item_ids:
        cached = metadata.get(followup_item_id, {})
        row = {"followup_item_id": followup_item_id}
        for key in keys:
            row[key] = cached.get(key) if isinstance(cached, dict) else None
        rows.append(row)
    return pd.DataFrame(rows, columns=["followup_item_id", *keys])


def _save_cache(cache_path, cache):
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = cache_path.with_suffix(cache_path.suffix + ".tmp")
    serialized = json.dumps(cache, ensure_ascii=False, indent=2)
    temporary_path.write_text(serialized, encoding="utf-8")
    try:
        temporary_path.replace(cache_path)
    except PermissionError:
        # Cloud-sync tools can lock the existing destination against os.replace().
        # Keep the valid temporary checkpoint until direct writing succeeds.
        cache_path.write_text(serialized, encoding="utf-8")
        try:
            temporary_path.unlink()
        except OSError:
            pass
