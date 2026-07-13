# OpenAlex API Tools

Python tools for working with [OpenAlex](https://openalex.org/) works metadata.

The project has two main functionalities:

- `get_works`: get OpenAlex work records directly.
- `enrich_works`: enrich an Excel spreadsheet of publication records.

## Setup

Install dependencies:

```bash
pip install -r requirements.txt
```

Create a `.env` file from `.env.example` and set your OpenAlex API key:

```text
OPENALEX_API_KEY=your_openalex_api_key_here
```

You can edit the `DEFAULT_*` values at the top of `main.py`, or override them
from the command line.

## Functionality 1: Get Works

Use `get_works` when you want to request OpenAlex work records directly, without
using a spreadsheet.

Input can be:

- one DOI
- one OpenAlex work ID
- comma-separated DOI/OpenAlex IDs
- semicolon-separated OpenAlex filters

Get one work by OpenAlex ID:

```python
DEFAULT_GET_WORKS_INPUT = "W2741809807"
DEFAULT_GET_WORKS_KEYS = [
    "id",
    "doi",
    "title",
    "publication_date",
    "cited_by_count",
]
```

Get one work by DOI:

```python
DEFAULT_GET_WORKS_INPUT = "10.7717/peerj.4375"
DEFAULT_GET_WORKS_KEYS = [
    "id",
    "doi",
    "title",
    "publication_date",
]
```

Get multiple works:

```python
DEFAULT_GET_WORKS_INPUT = "W2741809807,W2125284466"
DEFAULT_GET_WORKS_KEYS = [
    "id",
    "title",
]
```

Get works by filters:

Filtering input uses `field:value` pairs. Add multiple filters by separating
them with semicolons:

```text
field_1:value_1;field_2:value_2
```

For example, get works from one institution in a date range:

```python
DEFAULT_GET_WORKS_INPUT = "institutions.id:I145872427;from_publication_date:2025-01-01;to_publication_date:2025-12-31"
DEFAULT_GET_WORKS_KEYS = [
    "id",
    "title",
    "publication_date",
    "cited_by_count",
]
```

Another example, get works that cite a specific DOI or OpenAlex work:

```python
DEFAULT_GET_WORKS_INPUT = "cites:10.7717/peerj.4375"
DEFAULT_GET_WORKS_KEYS = [
    "id",
    "doi",
    "title",
    "publication_date",
    "cited_by_count",
]
```

If no output file is provided, `get_works` writes:

- `openalex_works.json`
- `openalex_works.xlsx`

## Functionality 2: Enrich Works

Use `enrich_works` when you have an Excel spreadsheet with publication records
and want to add OpenAlex metadata.

Before running spreadsheet enrichment, choose:

- `input file`: Excel workbook with one row per publication.
- `id column`: column containing DOI values or OpenAlex work IDs.
- `mode`: `full`, `enrich`, or `followup`.
- `output format`: `json` or `excel`.
- `output file`: where the enriched result should be written.
- `keys`: OpenAlex fields to add to the main publication rows.
- `follow-up field`: nested OpenAlex list field that contains IDs needing another request.
- `follow-up mode`: `resume_cache` or `build_cache`.
- `follow-up keys`: OpenAlex fields to fetch for every item in the follow-up field.

### Enrichment Modes

`full` first enriches the input publication rows and then runs the follow-up
workflow.

`enrich` enriches the input publication rows directly with selected OpenAlex
fields.

`followup` first fetches IDs from a nested OpenAlex list field and then requests
extra metadata for each item in that list.

### Follow-Up Requests

`referenced_works` is the default example follow-up field. You can replace it
with another OpenAlex list field and choose your own follow-up keys.

Follow-up cache modes:

- `resume_cache`: reuse existing cache files and fetch only missing items.
- `build_cache`: rebuild the follow-up cache from the full input file.

Direct enrichment example:

```bash
python main.py --workflow enrich_works --input publication_details.xlsx --id-column DOI --mode enrich --keys title publication_date cited_by_count --format json
```

Full enrichment example:

```bash
python main.py --workflow enrich_works --input publication_details.xlsx --id-column DOI --mode full --format json
```

Follow-up example using `referenced_works`:

```bash
python main.py --workflow enrich_works --input publication_details.xlsx --id-column DOI --mode followup --followup-field referenced_works --followup-mode resume_cache --followup-keys primary_location.source.display_name primary_location.source.issn
```

If no output file is provided, `enrich_works` writes:

- `publication_details_enriched.json`
- `publication_details_enriched.xlsx`

## Input File For Enrichment

The input file should be an Excel workbook (`.xlsx`) with one row per
publication. It must contain a column with DOI values or OpenAlex work IDs.

Common ID column examples:

- `DOI`
- `OpenAlex ID`

## Output

The script writes JSON or Excel output. Use `--format json` or `--format excel`.
Use `--output` to choose a custom output path.

## Caches

Follow-up requests can create local cache files so long runs can continue without
starting over. Cache files are ignored by git and should not be published.

## Privacy

Do not publish local spreadsheets, `.env` files, API caches, editor folders,
personal notes, or `__pycache__` folders. The `.gitignore` file excludes these
by default.

## License

MIT License. See [LICENSE](LICENSE).
