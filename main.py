from argparse import ArgumentParser, RawTextHelpFormatter
from pathlib import Path
import json


"""
*** USER INPUT / SETTINGS ***

This script works with OpenAlex works metadata.

What you need to choose before running:
- WORKFLOW: choose `get_works` or `enrich_works`.
- OUTPUT_FORMAT: choose `json` or `excel`.
- OUTPUT_FILE: choose where the result should be written.
- GET_WORKS_INPUT: DOI, OpenAlex work ID, or OpenAlex filters for direct lookup.
- GET_WORKS_KEYS: OpenAlex fields to return for direct lookup.
- INPUT_FILE: Excel spreadsheet with one row per publication.
- ID_COLUMN: spreadsheet column containing DOI values or OpenAlex work IDs.
- RUN_MODE: choose `full`, `enrich`, or `followup` for spreadsheet enrichment.
- ENRICH_KEYS: OpenAlex fields to add to the main publication rows.
- FOLLOWUP_FIELD: nested OpenAlex list field that needs extra requests.
- FOLLOWUP_MODE: choose `resume_cache` to reuse cache or `build_cache` to rebuild it.
- FOLLOWUP_KEYS: OpenAlex fields to fetch for every follow-up item.

Workflows:
- `get_works`: get OpenAlex work records directly by DOI, OpenAlex ID, or filters.
- `enrich_works`: enrich an Excel spreadsheet with OpenAlex works metadata.

Enrichment modes:
- `full`: run `enrich`, then run `followup`.
- `enrich`: enrich the input publication rows directly with ENRICH_KEYS.
- `followup`: fetch IDs from FOLLOWUP_FIELD, then request FOLLOWUP_KEYS for
  each item in that field.

Follow-up example:
- `referenced_works` is the default example FOLLOWUP_FIELD.
- You can replace it with another OpenAlex list field when needed.
- Then choose FOLLOWUP_KEYS for the metadata you want about each follow-up item.

Follow-up cache modes:
- `resume_cache`: reuse existing cache files and fetch only missing items.
- `build_cache`: rebuild the follow-up cache from the full input file.

You can edit the DEFAULT_* values below, or override them from the command line.
Run `python main.py --help` to see all command-line options.
"""


# *** CHOOSE MAIN WORKFLOW ***
# 'get_works' or 'enrich_works'
DEFAULT_WORKFLOW = "enrich_works"

# *** CHOOSE GET_WORKS WORKFLOW SETTINGS ***
#DEFAULT_GET_WORKS_INPUT = "10.7717/peerj.4375"
DEFAULT_GET_WORKS_INPUT = "institutions.id:I145872427;from_publication_date:2026-07-01;to_publication_date:2026-07-14"
DEFAULT_GET_WORKS_KEYS = [
    "id",
    "doi",
    "title",
    "publication_date",
    "cited_by_count",
]

# *** CHOOSE ENRICH_WORKS WORKFLOW SETTINGS ***
DEFAULT_INPUT_FILE = Path("publication_details.xlsx")
DEFAULT_ID_COLUMN = "DOI"
DEFAULT_LIMIT = None

# *** CHOOSE SPREADSHEET ENRICHMENT RUN TYPE ***
DEFAULT_RUN_MODE = "full"

# *** CHOOSE YOUR OUTPUT ***
DEFAULT_OUTPUT_FORMAT = "json"
DEFAULT_OUTPUT_FILE = None

# *** CHOOSE MAIN PUBLICATION ENRICHMENT FIELDS ***
DEFAULT_ENRICH_KEYS = [
    "id",
    "title",
    "publication_date",
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
    "cited_by_percentile_year",
    "primary_topic",
    "topics",
    "sustainable_development_goals",
    "awards",
    "funders",
    "referenced_works_count",
    "counts_by_year",
]

# *** CHOOSE FOLLOW-UP REQUEST SETTINGS ***
# `referenced_works` is only an example. Replace it with another OpenAlex list
# field if that is the field you want to follow up.
DEFAULT_FOLLOWUP_FIELD = "referenced_works"
DEFAULT_FOLLOWUP_MODE = "resume_cache"
DEFAULT_FOLLOWUP_KEYS = [
    "primary_location.source.display_name",
    "primary_location.source.issn",
]


WORKFLOWS = ("get_works", "enrich_works")
RUN_MODES = ("full", "enrich", "followup")
FOLLOWUP_MODES = ("build_cache", "resume_cache")
OUTPUT_FORMATS = ("json", "excel")
DEFAULT_OUTPUT_BASENAMES = {
    "get_works": "openalex_works",
    "enrich_works": "publication_details_enriched",
}


def build_parser():
    parser = ArgumentParser(
        description=(
            "Get OpenAlex works or enrich publication spreadsheets.\n\n"
            "Workflows:\n"
            "  get_works    = get OpenAlex work records directly\n"
            "  enrich_works = enrich a spreadsheet of publication records\n\n"
            "Enrichment modes:\n"
            "  full     = run enrich first, then run followup\n"
            "  enrich   = add OpenAlex fields to the input publication rows\n"
            "  followup = fetch IDs from a nested list field, then enrich those IDs"
        ),
        formatter_class=RawTextHelpFormatter,
    )

    workflow_group = parser.add_argument_group("Workflow")
    workflow_group.add_argument(
        "--workflow",
        choices=WORKFLOWS,
        default=DEFAULT_WORKFLOW,
        help="Choose `get_works` for direct lookup or `enrich_works` for spreadsheets.",
    )

    get_group = parser.add_argument_group("Get Works")
    get_group.add_argument(
        "--get-input",
        default=DEFAULT_GET_WORKS_INPUT,
        help=(
            "DOI, OpenAlex work ID, comma-separated IDs, or semicolon-separated "
            "filters such as institutions.id:I145872427;from_publication_date:2026-01-01."
        ),
    )

    input_group = parser.add_argument_group("Input")
    input_group.add_argument(
        "-i",
        "--input",
        type=Path,
        default=DEFAULT_INPUT_FILE,
        help="Input Excel file with publication records.",
    )
    input_group.add_argument(
        "--id-column",
        default=DEFAULT_ID_COLUMN,
        help="Column containing DOI values or OpenAlex work IDs.",
    )
    input_group.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_LIMIT,
        help="Process only the first N rows. Useful for testing.",
    )

    run_group = parser.add_argument_group("Run Mode")
    run_group.add_argument(
        "--mode",
        choices=RUN_MODES,
        default=DEFAULT_RUN_MODE,
        help=(
            "full = enrich and followup; enrich = direct enrichment only; "
            "followup = nested-list requests only."
        ),
    )

    output_group = parser.add_argument_group("Output")
    output_group.add_argument(
        "-f",
        "--format",
        choices=OUTPUT_FORMATS,
        default=DEFAULT_OUTPUT_FORMAT,
        help="Output format.",
    )
    output_group.add_argument(
        "-o",
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_FILE,
        help="Output file. If omitted, a default generic name is used.",
    )

    enrich_group = parser.add_argument_group("Publication Enrichment Keys")
    enrich_group.add_argument(
        "--keys",
        nargs="+",
        default=None,
        metavar="KEY",
        help=(
            "OpenAlex fields to return. If omitted, get_works uses "
            "DEFAULT_GET_WORKS_KEYS and enrich_works uses DEFAULT_ENRICH_KEYS."
        ),
    )

    followup_group = parser.add_argument_group("Follow-Up Requests")
    followup_group.add_argument(
        "--followup-field",
        default=DEFAULT_FOLLOWUP_FIELD,
        help=(
            "Nested OpenAlex list field containing IDs to request next. "
            "Default example: referenced_works."
        ),
    )
    followup_group.add_argument(
        "--followup-mode",
        choices=FOLLOWUP_MODES,
        default=DEFAULT_FOLLOWUP_MODE,
        help=(
            "resume_cache = reuse cache and fetch only missing items; "
            "build_cache = rebuild from the full input file."
        ),
    )
    followup_group.add_argument(
        "--followup-keys",
        nargs="+",
        default=DEFAULT_FOLLOWUP_KEYS,
        metavar="KEY",
        help="OpenAlex fields to fetch for each item found in --followup-field.",
    )

    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)

    keys = normalize_key_list(args.keys)
    followup_keys = normalize_key_list(args.followup_keys)

    if args.workflow == "get_works":
        output_path = args.output or default_output_path(args.workflow, args.format)
        get_keys = keys or DEFAULT_GET_WORKS_KEYS
        result = get_works(args.get_input, get_keys)
        print_get_works_summary(args.get_input, args.format, output_path, get_keys)
        export_results(result, args.format, output_path)
        print(f"Wrote output file: {output_path}", flush=True)
        return 0

    keys = keys or DEFAULT_ENRICH_KEYS
    input_path = args.input
    output_path = args.output or default_output_path(args.workflow, args.format)
    print(f"Loading input file: {input_path}", flush=True)
    df = load_input(input_path)
    if args.limit is not None:
        if args.limit <= 0:
            raise SystemExit("--limit must be greater than zero")
        df = df.head(args.limit)

    validate_input(df, args.id_column)
    print_run_summary(
        df=df,
        id_column=args.id_column,
        mode=args.mode,
        output_format=args.format,
        output_path=output_path,
        keys=keys,
        followup_field=args.followup_field,
        followup_mode=args.followup_mode,
        followup_keys=followup_keys,
    )

    result = process_data(
        df=df,
        id_column=args.id_column,
        mode=args.mode,
        keys=keys,
        followup_field=args.followup_field,
        followup_mode=args.followup_mode,
        followup_keys=followup_keys,
    )

    export_results(result, args.format, output_path)
    print(f"Wrote output file: {output_path}", flush=True)
    return 0


def load_input(path: Path):
    import pandas as pd

    if not path.exists():
        raise SystemExit(
            f"Input file not found: {path}\n"
            "Edit DEFAULT_INPUT_FILE in main.py or pass --input with your spreadsheet."
        )
    return pd.read_excel(path)


def validate_input(df, id_column):
    if id_column not in df.columns:
        available = ", ".join(str(column) for column in df.columns)
        raise SystemExit(
            f"ID column not found: {id_column}\n"
            f"Available columns: {available}"
        )


def print_run_summary(
    df,
    id_column,
    mode,
    output_format,
    output_path,
    keys,
    followup_field,
    followup_mode,
    followup_keys,
):
    print("OpenAlex enrichment")
    print(f"  rows loaded:      {len(df):,}")
    print(f"  id column:        {id_column}")
    print(f"  mode:             {mode}")
    print(f"  output format:    {output_format}")
    print(f"  output file:      {output_path}")
    print(f"  enrichment keys:  {', '.join(keys)}")
    if mode in {"full", "followup"}:
        print(f"  follow-up field:  {followup_field}")
        print(f"  follow-up mode:   {followup_mode}")
        print(f"  follow-up keys:   {', '.join(followup_keys)}")


def print_get_works_summary(get_input, output_format, output_path, keys):
    print("OpenAlex get works")
    print(f"  input:           {get_input}")
    print(f"  output format:   {output_format}")
    print(f"  output file:     {output_path}")
    print(f"  keys:            {', '.join(keys)}")


def get_works(raw_input, keys):
    from modules.entities import Works

    get_input = parse_get_works_input(raw_input)
    get_input = resolve_work_id_filters(get_input, Works)
    print("Starting get_works workflow.", flush=True)
    return Works.get(get_input, keys)


def parse_get_works_input(raw_input):
    if isinstance(raw_input, list):
        return raw_input
    if not isinstance(raw_input, str) or not raw_input.strip():
        raise ValueError("get works input must be provided")

    raw_input = raw_input.strip()
    if _looks_like_filter_input(raw_input):
        filters = []
        for item in raw_input.split(";"):
            if not item.strip():
                continue
            if ":" not in item:
                raise ValueError(f"Invalid filter: {item}")
            key, value = item.split(":", 1)
            filters.append((key.strip(), value.strip()))
        return filters

    if "," in raw_input:
        return [item.strip() for item in raw_input.split(",") if item.strip()]

    return raw_input


def resolve_work_id_filters(get_input, works):
    if not _is_filter_list(get_input):
        return get_input

    resolved_filters = []
    for key, value in get_input:
        if key == "cites" and _looks_like_doi(value):
            print(f"Resolving DOI for cites filter: {value}", flush=True)
            value = resolve_openalex_work_id(value, works)
        resolved_filters.append((key, value))
    return resolved_filters


def resolve_openalex_work_id(identifier, works):
    work = works.get(identifier, ["id"])
    if not isinstance(work, dict) or not work.get("id"):
        raise ValueError(f"Could not resolve OpenAlex work ID for: {identifier}")
    return work["id"].rstrip("/").split("/")[-1]


def _is_filter_list(value):
    return isinstance(value, list) and all(
        isinstance(item, tuple) and len(item) == 2
        for item in value
    )


def _looks_like_doi(value):
    if not isinstance(value, str):
        return False
    value = value.strip().lower()
    return value.startswith("10.") or "doi.org/10." in value


def _looks_like_filter_input(value):
    if ":" not in value:
        return False
    if value.lower().startswith(("http://", "https://")):
        return False
    first_key = value.split(";", 1)[0].split(":", 1)[0].strip()
    return bool(first_key) and all(
        character.isalnum() or character in "._-"
        for character in first_key
    )


def process_data(
    df,
    id_column,
    mode,
    keys,
    followup_field=DEFAULT_FOLLOWUP_FIELD,
    followup_mode=DEFAULT_FOLLOWUP_MODE,
    followup_keys=None,
):
    if mode == "full":
        from modules.entities import Works
        from modules.follow_up import add_followup_items, enrich_followup_occurrences

        print(f"Starting full mode for {len(df):,} rows.", flush=True)
        df = Works.enrich(df, keys, column_name=id_column)
        df = add_followup_items(
            df,
            source_field=followup_field,
            column_name=id_column,
            refresh=followup_mode == "build_cache",
        )
        return enrich_followup_occurrences(
            df,
            source_field=followup_field,
            keys=followup_keys or DEFAULT_FOLLOWUP_KEYS,
            citing_column=id_column,
        )

    if mode == "enrich":
        from modules.entities import Works

        print(f"Starting enrich mode for {len(df):,} rows.", flush=True)
        return Works.enrich(df, keys, column_name=id_column)

    if mode == "followup":
        from modules.follow_up import add_followup_items, enrich_followup_occurrences

        print(
            f"Starting followup mode for {len(df):,} rows using {followup_field}.",
            flush=True,
        )
        df = add_followup_items(
            df,
            source_field=followup_field,
            column_name=id_column,
            refresh=followup_mode == "build_cache",
        )
        return enrich_followup_occurrences(
            df,
            source_field=followup_field,
            keys=followup_keys or DEFAULT_FOLLOWUP_KEYS,
            citing_column=id_column,
        )

    raise ValueError('mode must be "full", "enrich", or "followup"')


def normalize_key_list(raw_keys):
    if not raw_keys:
        return []
    if isinstance(raw_keys, str):
        raw_keys = [raw_keys]
    return [key.strip() for key in raw_keys if key and key.strip()]


def default_output_path(workflow: str, output_format: str) -> Path:
    basename = DEFAULT_OUTPUT_BASENAMES[workflow]
    return Path(f"{basename}.{output_format.lower()}")


def export_results(df, output_format, output_path):
    output_format = output_format.lower()
    output_path = Path(output_path)

    if not hasattr(df, "to_json"):
        df = normalize_api_result(df)

    if output_format == "excel":
        _prepare_for_excel(df).to_excel(
            output_path,
            sheet_name="OpenAlex Enriched Data",
            index=False,
        )
        return

    if output_format == "json":
        data = json.loads(df.to_json(orient="records", date_format="iso"))
        output_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return

    raise ValueError('output_format must be either "excel" or "json"')


def normalize_api_result(result):
    import pandas as pd

    if isinstance(result, list):
        return pd.DataFrame(result)
    if isinstance(result, dict):
        return pd.DataFrame([result])
    return pd.DataFrame([{"result": result}])


def _prepare_for_excel(df):
    from modules.utils import Excel

    return df.apply(lambda column: column.map(Excel.coerce_for_excel))


if __name__ == "__main__":
    raise SystemExit(main())
