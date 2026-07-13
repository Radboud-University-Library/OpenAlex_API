# OpenAlex API Enrichment Tools

Python tools for enriching publication spreadsheets with metadata from the
[OpenAlex](https://openalex.org/) API.

The main script reads an Excel spreadsheet with DOI values or OpenAlex work IDs,
requests selected OpenAlex fields, and writes enriched output as JSON or Excel.
It can also make configurable follow-up requests against nested OpenAlex list
fields. `referenced_works` is included as an example follow-up field, not as the
only possible follow-up request.

## What You Need To Choose

Before running the script, choose these inputs in `main.py` or with command-line
arguments:

- `input file`: Excel workbook with one row per publication.
- `id column`: column containing DOI values or OpenAlex work IDs.
- `run mode`: `enrich` or `followup`.
- `output format`: `json` or `excel`.
- `output file`: where the enriched result should be written.
- `enrichment keys`: OpenAlex fields to add to the main publication rows.
- `follow-up field`: nested OpenAlex list field that contains IDs needing a second request.
- `follow-up mode`: `build` or `refresh` for the follow-up cache.
- `follow-up keys`: OpenAlex fields to fetch for every item in the follow-up field.

## Modes

`enrich` enriches the input publication rows directly with the fields listed in
`DEFAULT_ENRICH_KEYS` or passed with `--keys`.

`followup` first fetches IDs from a nested OpenAlex list field and then requests
extra metadata for each item in that list. The default example is
`referenced_works`. To follow up another list field, set `DEFAULT_FOLLOWUP_FIELD`
or pass `--followup-field`.

Follow-up cache modes:

- `build`: reuse existing cache files and fetch only missing items.
- `refresh`: rebuild the follow-up cache from the input file.

## Quick Start

Install dependencies:

```bash
pip install -r requirements.txt
```

Create a `.env` file from `.env.example` and set your OpenAlex contact email:

```text
OPENALEX_EMAIL=your.name@example.org
```

Edit the `DEFAULT_*` values at the top of `main.py`, then run:

```bash
python main.py
```

You can also override settings from the command line.

Direct enrichment example:

```bash
python main.py --input publication_details.xlsx --id-column DOI --mode enrich --keys title publication_date cited_by_count --format json
```

Follow-up example using `referenced_works`:

```bash
python main.py --input publication_details.xlsx --id-column DOI --mode followup --followup-field referenced_works --followup-mode build --followup-keys primary_location.source.display_name primary_location.source.issn
```

## Input File

The input file should be an Excel workbook (`.xlsx`) with one row per
publication. It must contain a column with DOI values or OpenAlex work IDs.

Common ID column examples:

- `DOI`
- `doi`
- `openalex_id`
- `OpenAlex ID`

## Output

The script writes either JSON or Excel output. If no output path is provided, it
uses a generic default name:

- `publication_details_enriched.json`
- `publication_details_enriched.xlsx`

## Caches

Follow-up requests can create local cache files so long runs can continue without
starting over. Cache files are ignored by git and should not be published.

## Privacy

Do not publish local spreadsheets, `.env` files, API caches, editor folders,
personal notes, or `__pycache__` folders. The `.gitignore` file excludes these
by default.

## License

MIT License. See [LICENSE](LICENSE).
