# Current Results

## Choose Provider and Sample

| Provider | 100 random datasets | Top-10 datasets |
| --- | --- | --- |
| OpenAI (required web search) | [Results and files](openai/random100/README.md) | [Results and files](openai/top10/README.md) |
| Gemini (search enabled) | [Results and files](gemini/random100/README.md) | [Results and files](gemini/top10/README.md) |

Each link opens a readable table for V1/V2/V3/V6 and the five associated CSVs.
No provider filtering is needed: each folder contains only its named provider
and sample. For side-by-side comparison, use the interpretation below.

## Local Source Folders

All source results are consolidated under `output/current_results_sources/`:

| Publication folder | Source folder, relative to the repository root |
| --- | --- |
| `openai/random100/` | `output/current_results_sources/openai/random100/` |
| `openai/top10/` | `output/current_results_sources/openai/top10/` |
| `gemini/random100/` | `output/current_results_sources/gemini/random100/` |
| `gemini/top10/` | `output/current_results_sources/gemini/top10/` |

Source folders contain the variant subfolders and raw logs. They are local data,
excluded from GitHub; the publication folders are generated from them.

The previous optional-search OpenAI run is historical and is stored separately
under `output/archive/openai_optional_search_random100/`, not among these sources.

Start with [INTERPRETATION.md](INTERPRETATION.md) for the setup, results tables,
metric explanations, and limitations.

A separate [live link-validation audit](link_validation/README.md) checks the
OpenAI title-only source matches. It does not change the main metrics and shows
why an unconfirmed identifier should not automatically be called an invalid link.

Both providers and both samples were reevaluated after correcting SDN identifier
extraction and DOI conversion. Saved prompts, API responses, and relevance sets
are unchanged; only evaluation-derived labels and counts were refreshed.

This is the current publication package for the random-100 and top-10 samples,
using V1, V2, V3, and V6. It includes only the completed required-search OpenAI
run `20261123T145051Z_d675e7f7` and the saved Gemini responses. Earlier OpenAI
runs, OpenWebUI comparisons, and download-focused title experiments are excluded.

## Search Conditions

- OpenAI: search required; confirmed search execution for all 610 requests.
- Gemini: Google Search enabled, but not required. Only one final random-100
  response records grounding (V6 query 80); none of the top-10 final responses
  record grounding. Missing grounding is labeled as no recorded search evidence.

These conditions are not equivalent. The results compare the tested provider
configurations, not isolated model capabilities under identical search conditions.

## Files

Each of the four provider/sample folders contains the same five
semicolon-separated CSVs:

| File | Contents |
| --- | --- |
| `summary.csv` | Query-level discovery counts and rates, empty responses, errors, and search-evidence counts |
| `queries.csv` | Query metadata and complete system/user prompts, with provider and variant |
| `returned_items.csv` | Every returned item, rank, title, link, justification, matching and relevance labels |
| `per_request.csv` | One row per prompt/provider/variant, including empty responses, metrics, and search evidence |
| `qrels.csv` | Relevant dataset identifiers, titles, and topic/country/time metadata; prompts are kept in `queries.csv` |

Use `provider`, `variant`, and `query_id` together to connect these files.
For returned items, `rank` identifies the position in the response.
`evaluation_available=0` means the item has no corresponding evaluated row;
blank labels should not be interpreted as a confirmed non-relevant judgment.

`provenance.json` records the source paths and SHA-256 checksums used to build
the package. It contains no API keys. Large raw API logs remain in `output/` and
are not included in this publication folder.

## Reading the Metrics

- Original-dataset discovery, identifier-confirmed: queries retrieving the original source dataset through
  the evaluator's identifier/catalogue-equivalence matching rules.
- Relevant GESIS dataset discovery, identifier-confirmed: queries retrieving at least one identifier-matched
  dataset in the metadata-filter relevance set.
- Original/relevant dataset discovery with identifier or title matching: broader
  measures also allowing accepted title-based matches.
- A discovery rate is the percentage of queries finding at least one qualifying
  dataset within the evaluated first 10 results. Multiple items in one response
  do not create multiple successful queries.
- All rates include every planned query in the denominator, including empty
  responses and API errors.
- No response-item limit was included in the prompts. Every returned item is
  exported, but the existing retrieval metrics evaluate the top 10 positions.
- `link_valid` is catalogue-matching evidence, not an independent live-link test.

V2 generates multiple queries per dataset; its rates are query-level, not the
percentage of unique source datasets found. Historical V6 wording differs
between providers. See the interpretation for these and other limitations.

CSV column names remain technical and unchanged:

| Report measure | CSV count column | CSV rate column |
| --- | --- | --- |
| Original dataset, identifier-confirmed | `strict_source_hits` | `strict_source_rate` |
| Original dataset, identifier or title | `source_hits` | `source_rate` |
| Relevant GESIS dataset, identifier-confirmed | `strict_gesis_hits` | `strict_gesis_rate` |
| Relevant GESIS dataset, identifier or title | `gesis_hits` | `gesis_rate` |

## Single Source of Truth

- The selected `output/` runs hold original responses and evaluated results.
- This folder is a generated publication view, not an independently maintained
  copy. Do not manually edit its CSVs or `INTERPRETATION.md`.
- Change matching rules in `src/match_and_eval.py`, then reevaluate the selected
  runs before rebuilding. Change interpretation wording in
  `scripts/build_publication_report.py`, then rebuild.
- `README.md` contains navigation and methodology, not a second results table.
- README files are generated from `scripts/report_templates/`; edit those
  templates, not the generated files here.
- Historical report builders and prompt-export scripts are retired and stored
  locally under `output/archive/`. Use `scripts.build_publication_report` here.

Check consistency before publishing:

```powershell
python -m scripts.build_publication_report --check
```

This checks source hashes, evaluation-code hashes, regenerated CSVs and
interpretation, plus supplementary link-audit dependencies and exported files.
It exits with an error if a stale or edited artifact is found, without changing
the report or calling an API. Source files in `output/` must be available locally.

## Rebuild

From the repository root, with the selected source files available:

```powershell
python -m scripts.build_publication_report --include-link-audit
```

This reads saved results only and makes no API calls or network requests. It
refreshes the CSVs, provenance, interpretation, and README files, and rebuilds
the supplementary audit using cached evidence. No evaluation is rerun. Data
inputs are all under `output/current_results_sources/`, including `_support/`.

The SDN correction was applied using the matching-only refresh documented in the
root README. Previous evaluation files and the publication package were backed
up under `output/archive/evaluation_refresh/20261124T103126254556Z/`.
