from argparse import ArgumentParser, RawTextHelpFormatter
from pathlib import Path
import json


"""
*** USER INPUT / SETTINGS ***

This script enriches a publication spreadsheet with OpenAlex metadata.

What you need to choose before running:
- INPUT_FILE: Excel spreadsheet with one row per publication.
- ID_COLUMN: spreadsheet column containing DOI values or OpenAlex work IDs.
- RUN_MODE: choose `enrich` or `followup`.
- OUTPUT_FORMAT: choose `json` or `excel`.
- OUTPUT_FILE: choose where the result should be written.
- ENRICH_KEYS: OpenAlex fields to add to the main publication rows.
- FOLLOWUP_FIELD: nested OpenAlex list field that needs extra requests.
- FOLLOWUP_MODE: choose `build` or `refresh` for the follow-up cache.
- FOLLOWUP_KEYS: OpenAlex fields to fetch for every follow-up item.

Modes:
- `enrich`: enrich the input publication rows directly with ENRICH_KEYS.
- `followup`: fetch IDs from FOLLOWUP_FIELD, then request FOLLOWUP_KEYS for
  each item in that field.

Follow-up example:
- `referenced_works` is the default example FOLLOWUP_FIELD.
- You can replace it with another OpenAlex list field when needed.
- Then choose FOLLOWUP_KEYS for the metadata you want about each follow-up item.

Follow-up cache modes:
- `build`: reuse existing cache files and fetch only missing items.
- `refresh`: rebuild the follow-up cache from the input file.

You can edit the DEFAULT_* values below, or override them from the command line.
Run `python main.py --help` to see all command-line options.
"""


# *** CHOOSE YOUR INPUT ***
DEFAULT_INPUT_FILE = Path("publication_details.xlsx")
DEFAULT_ID_COLUMN = "DOI"
DEFAULT_LIMIT = None

# *** CHOOSE THE RUN TYPE ***
DEFAULT_RUN_MODE = "enrich"

# *** CHOOSE YOUR OUTPUT ***
DEFAULT_OUTPUT_FORMAT = "json"
DEFAULT_OUTPUT_BASENAME = "publication_details_enriched"
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
DEFAULT_FOLLOWUP_MODE = "build"
DEFAULT_FOLLOWUP_KEYS = [
    "primary_location.source.display_name",
    "primary_location.source.issn",
]


RUN_MODES = ("enrich", "followup")
FOLLOWUP_MODES = ("build", "refresh")
OUTPUT_FORMATS = ("json", "excel")
DEFAULT_OUTPUT_PATHS = {
    "excel": Path(DEFAULT_OUTPUT_BASENAME + ".xlsx"),
    "json": Path(DEFAULT_OUTPUT_BASENAME + ".json"),
}


def build_parser():
    parser = ArgumentParser(
        description=(
            "Enrich publication spreadsheets with OpenAlex metadata.\n\n"
            "Primary workflow:\n"
            "  1. choose the input file\n"
            "  2. choose the column with DOI/OpenAlex IDs\n"
            "  3. choose the OpenAlex keys to enrich\n"
            "  4. choose the run mode\n"
            "  5. optionally make follow-up requests against nested OpenAlex lists\n\n"
            "Modes:\n"
            "  enrich   = add OpenAlex fields to the input publication rows\n"
            "  followup = fetch IDs from a nested list field, then enrich those IDs"
        ),
        formatter_class=RawTextHelpFormatter,
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
        help="Choose `enrich` for direct enrichment or `followup` for nested-list requests.",
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
        default=DEFAULT_ENRICH_KEYS,
        metavar="KEY",
        help="OpenAlex fields to add in enrich mode. Nested fields can use dotted paths.",
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
        help="build = fetch missing cache items; refresh = rebuild the cache.",
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

    input_path = args.input
    output_path = args.output or default_output_path(args.format)
    keys = normalize_key_list(args.keys)
    followup_keys = normalize_key_list(args.followup_keys)

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
    if mode == "followup":
        print(f"  follow-up field:  {followup_field}")
        print(f"  follow-up mode:   {followup_mode}")
        print(f"  follow-up keys:   {', '.join(followup_keys)}")


def process_data(
    df,
    id_column,
    mode,
    keys,
    followup_field=DEFAULT_FOLLOWUP_FIELD,
    followup_mode=DEFAULT_FOLLOWUP_MODE,
    followup_keys=None,
):
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
            refresh=followup_mode == "refresh",
        )
        return enrich_followup_occurrences(
            df,
            source_field=followup_field,
            keys=followup_keys or DEFAULT_FOLLOWUP_KEYS,
            citing_column=id_column,
        )

    raise ValueError('mode must be "enrich" or "followup"')


def normalize_key_list(raw_keys):
    if not raw_keys:
        return []
    if isinstance(raw_keys, str):
        raw_keys = [raw_keys]
    return [key.strip() for key in raw_keys if key and key.strip()]


def default_output_path(output_format: str) -> Path:
    return DEFAULT_OUTPUT_PATHS[output_format.lower()]


def export_results(df, output_format, output_path):
    output_format = output_format.lower()
    output_path = Path(output_path)

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


def _prepare_for_excel(df):
    from modules.utils import Excel

    return df.apply(lambda column: column.map(Excel.coerce_for_excel))


if __name__ == "__main__":
    raise SystemExit(main())
