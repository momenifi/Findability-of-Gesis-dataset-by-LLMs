# LLM-Mediated Findability (GESIS)

This repo evaluates how well an OpenAI model surfaces and ranks GESIS datasets when queries are built from different metadata combinations. It compares two modes:

- `NO_WEB`: Model must not browse the web and uses only internal knowledge.
- `WEB_SEARCH`: Model uses the built-in `web_search` tool via the OpenAI Responses API.

## Setup

1. Install dependencies:

### Conda (optional but recommended)

```bash
conda create -n gesis-findability python=3.11
conda activate gesis-findability
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Set your API key:

```bash
set OPENWEBUI_API_KEY=YOUR_KEY
```

## Configuration

Edit `config.yaml`:

- `input_path`: path to your metadata file
- `input_format`: `csv` or `jsonl`
- `sample_per_variant`: number of queries per variant
- `query_variants`: V1-V5 templates
- `modes`: `NO_WEB` and/or `WEB_SEARCH`
- `model_no_web`, `model_web`: OpenAI models
- `top_k_return`: number of items to return per query
- `retrieval_for_candidates`: optional local candidate filtering
- `api_base_url`: optional base URL (for OpenWebUI use `https://ai-openwebui.gesis.org/api`)
- `api_key_env`: environment variable name for the API key

## Run

```bash
python -m src.generate_queries --config config.yaml
python -m src.run_llm --config config.yaml
python -m src.match_and_eval --config config.yaml
```

## Outputs

- `queries.csv`: generated queries
- `llm_results.csv`: ranked results per query
- `per_query_results.csv`: per-item matches and relevance
- `metrics_summary.csv`: metrics grouped by query variant and mode
- `logs/`: raw model responses

## Notes on Modes

- **NO_WEB**: The system prompt explicitly forbids web browsing. No tools are included in the request.
- **WEB_SEARCH**: The request includes `tools=[{"type":"web_search"}]` to enable built-in search. The prompt instructs the model to return only GESIS-hosted landing pages or DOIs.

If your API endpoint does not support the Responses API, the code will automatically fall back to Chat Completions. In that case, `WEB_SEARCH` cannot use built-in tools. When OpenWebUI is detected, `WEB_SEARCH` is removed automatically so results won’t be mislabeled.

If you want to use the OpenAI hosted API instead of OpenWebUI, set `api_base_url` to empty and set `api_key_env: OPENAI_API_KEY`, then export `OPENAI_API_KEY`.
