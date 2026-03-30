# Session Handover

## Project

This repo was set up to evaluate "LLM-mediated findability" of GESIS datasets.

Implemented pipeline:

1. Load GESIS metadata from CSV or JSONL.
2. Generate natural-language query variants from metadata fields.
3. Run an OpenAI-compatible model in `NO_WEB` and `WEB_SEARCH` modes.
4. Match returned items back to dataset IDs and compute evaluation metrics.

Main outputs:

- `queries.csv`
- `llm_results.csv`
- `per_query_results.csv`
- `metrics_summary.csv`
- `logs/`

## Files Added / Updated In This Session

- `config.yaml`
- `requirements.txt`
- `README.md`
- `src/__init__.py`
- `src/load_metadata.py`
- `src/generate_queries.py`
- `src/run_llm.py`
- `src/match_and_eval.py`

## What Each Script Does

### `src/load_metadata.py`

- Loads CSV or JSONL with pandas.
- Creates fallback columns:
  - `title`, `abstract`, `topic`, `methodology`, `country`, `universe`
  - `content_description`, `topics_stw`, `topics_thesoz`, `categories`
- Creates canonical `link` from `portal_url` or DOI.

### `src/generate_queries.py`

- Generates natural-language queries from metadata.
- Implemented variants:
  - `V1_TOPIC`
  - `V2_TOPIC_METHOD`
  - `V3_TOPIC_COUNTRY`
  - `V4_TOPIC_UNIVERSE`
  - `V5_TOPIC_TITLE`
- Removes empty queries.
- Filters out queries containing IDs, DOIs, or handles.
- Deduplicates by `(query_variant, normalized_query)`.
- Samples up to `sample_per_variant` per variant.

### `src/run_llm.py`

- Reads `queries.csv`.
- Calls the OpenAI Python SDK.
- Uses the Responses API when available.
- Falls back to Chat Completions if the endpoint does not support Responses.
- Parses JSON output and writes raw responses to `logs/`.
- Supports optional local BM25 candidate restriction.

Important implementation detail:

- `src/run_llm.py` now detects OpenWebUI and removes `WEB_SEARCH` automatically because OpenWebUI does not support the built-in `web_search` tool used by the Responses API.

### `src/match_and_eval.py`

- Matches returned items to datasets by:
  - exact DOI
  - exact portal URL
  - fuzzy title match using `rapidfuzz`
- Builds silver qrels with TF-IDF similarity over:
  - `abstract`
  - `content_description`
  - `categories`
  - `topics_stw`
  - `topics_thesoz`
  - `universe`
- Computes:
  - `precision_at_k`
  - `recall_at_k`
  - `mrr`
  - `ndcg_at_k`
  - `link_valid_rate`
  - `off_repo_rate`

## Current Config

`config.yaml` currently points to:

- `input_path: random_100_datasets_full_metadata.csv`
- `input_format: csv`
- `api_base_url: https://ai-openwebui.gesis.org/api`
- `api_key_env: OPENWEBUI_API_KEY`

This means the repo is currently configured for GESIS-hosted OpenWebUI, not OpenAI-hosted API.

## Important Limitation

OpenWebUI does not support the Responses API tool call needed for true `WEB_SEARCH`.

What this means:

- `NO_WEB` works as intended.
- True `WEB_SEARCH` requires OpenAI-hosted API with built-in `web_search`.
- On OpenWebUI, the code now removes `WEB_SEARCH` automatically to avoid mislabeled results.

If later you want true browsing:

- set `api_base_url` to empty
- set `api_key_env: OPENAI_API_KEY`
- export `OPENAI_API_KEY`

## Existing Output Files

Present in the repo:

- `queries.csv`
- `llm_results.csv`
- `per_query_results.csv`
- `metrics_summary.csv`
- `logs/`

These files were generated during the session, but there is one caveat:

- some earlier output rows include `WEB_SEARCH` labels from before the final OpenWebUI guard was added
- those rows do not represent real web search; they came from fallback chat behavior

To get clean results with the current code and current OpenWebUI setup, rerun:

```bash
python -m src.generate_queries --config config.yaml
python -m src.run_llm --config config.yaml
python -m src.match_and_eval --config config.yaml
```

After rerunning on OpenWebUI, only `NO_WEB` should be executed.

## Current Result Snapshot

The existing `metrics_summary.csv` contains both `NO_WEB` and `WEB_SEARCH` rows from the earlier run. Treat the `WEB_SEARCH` rows as invalid under OpenWebUI.

Example issues visible in current outputs:

- `link_valid_rate` is often `0.0`
- `off_repo_rate` is high in several variants
- `metrics_summary.csv` currently includes an averaged `query_id` column, which is not analytically useful and should be removed in a cleanup pass

## Commands Used

Main workflow:

```bash
python -m src.generate_queries --config config.yaml
python -m src.run_llm --config config.yaml
python -m src.match_and_eval --config config.yaml
```

## Validation Status

- Files were implemented and output files were produced.
- The OpenWebUI compatibility path was adjusted after runtime errors:
  - `response_format` unsupported
  - Responses endpoint returned `405 Method Not Allowed`
- No formal test suite was added.
- I did not run a fresh end-to-end regeneration after the final `WEB_SEARCH` removal logic was added.

## Recommended Next Steps

1. Rerun the full pipeline with the current code to regenerate clean `NO_WEB` outputs.
2. Remove `query_id` from `metrics_summary.csv` aggregation logic in `src/match_and_eval.py`.
3. Decide whether future runs should target:
   - OpenWebUI for `NO_WEB` only
   - OpenAI-hosted API for real `WEB_SEARCH`
4. If comparing true web vs no-web is required, switch credentials and endpoint to OpenAI-hosted API.

## Environment Notes

- This folder is not a git repository.
- A conda environment was recommended:

```bash
conda create -n gesis-findability python=3.11
conda activate gesis-findability
pip install -r requirements.txt
```

## Extra Files In Workspace

Metadata files present:

- `random_100_datasets_full_metadata.csv`
- `random_100_datasets_full_metadata 1st round.csv`

Helper file present:

- `test_openwebui.py`

That helper script was used as the reference for OpenWebUI configuration:

- base URL family: `https://ai-openwebui.gesis.org`
- auth env var: `OPENWEBUI_API_KEY`
