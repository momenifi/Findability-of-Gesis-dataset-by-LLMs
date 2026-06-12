# LLM-Mediated Findability (GESIS)

This repo evaluates how well a model surfaces and ranks GESIS datasets when queries are built from metadata-derived templates.

- `WEB_SEARCH`: Model uses web search during ranking.

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
- `qrels_input_path`: optional metadata file used for evaluation/qrels; use this to query a sample but evaluate against the full corpus
- `qrels_input_format`: format for `qrels_input_path`
- `output_dir`: folder for `queries.csv`, `llm_results.csv`, metrics, qrels, and logs
- `sample_per_variant`: number of queries per variant
- `query_variants`: configured query templates
- `time_format`: `years`, `span`, or `decade` for topic/country/time query wording
- `modes`: `WEB_SEARCH`
- `model_no_web`, `model_web`: model IDs
- `models_no_web`, `models_web`: optional lists of model IDs for model comparison; these override the single-model settings
- `top_k_return`: number of items to return per query
- `retrieval_for_candidates`: optional local candidate filtering
- `api_base_url`: optional base URL (for OpenWebUI use `https://ai-openwebui.gesis.org/api`)
- `api_key_env`: environment variable name for the API key
- `openwebui_web_search_mode`: for OpenWebUI `WEB_SEARCH`, use `tool_ids` unless your instance requires `features`
- `request_timeout_connect_seconds`, `request_timeout_read_seconds`: request time limits
- `request_max_retries`, `request_retry_backoff_seconds`: retry controls for slow or failed requests

## Run

```bash
python -m src.generate_queries --config config.yaml
python -m src.run_llm --config config.yaml
python -m src.match_and_eval --config config.yaml
```

## Outputs

Outputs are written under `output_dir`:

- `queries.csv`: generated queries
- `llm_results.csv`: ranked results per query
- `per_query_results.csv`: per-item matches and relevance
- `metrics_per_query.csv`: metrics per query
- `metrics_summary.csv`: metrics grouped by query variant and mode
- `qrels.csv`: relevant datasets used for evaluation
- `logs/`: raw model responses

## Notes on Modes

- **WEB_SEARCH** with OpenAI-hosted API: the request uses the Responses API with `tools=[{"type":"web_search"}]`.
- **WEB_SEARCH** with OpenWebUI: the request uses `POST /api/chat/completions` with `features.web_search=true`.

## Query Template

The current generator creates web-search queries from:

- `topic_en` or `topic`
- `countries_collection_en` or `countries_collection`
- `time_collection_years`

Template used:

```text
Can you find datasets related to [{topic}] in [{country}] during the [{time_collection_years}]?
```

`time_format` controls only the wording in the prompt:

- `years`: `["1971", "1972"]`
- `span`: `1971-1972`
- `decade`: `1970s`; cross-decade ranges become `1960s and 1970s`

The evaluation qrels still use the original exact `time_collection_years` values.

Configured variants:

- `V1_TOPIC_COUNTRY_TIME_ALL_TOPICS`: uses the full topic list.
- `V2_TOPIC_COUNTRY_TIME_SINGLE_TOPIC`: creates one query per topic item while keeping the same country list and time span.
- `V3_TITLE_ONLY`: uses only the dataset title instead of topic, country, and time span.

To test title-based query generation, temporarily set `query_variants` in `config.yaml` to:

```yaml
query_variants:
  - V3_TITLE_ONLY
```

Then regenerate queries:

```bash
python -m src.generate_queries --config config.yaml
```

To switch back to the previous topic-based configuration, restore:

```yaml
query_variants:
  - V1_TOPIC_COUNTRY_TIME_ALL_TOPICS
  - V2_TOPIC_COUNTRY_TIME_SINGLE_TOPIC
```

Pilot workflow:

1. Title baseline:

```yaml
output_dir: output/title_websearch
query_variants:
  - V3_TITLE_ONLY
```

2. Metadata discovery:

```yaml
output_dir: output/metadata_websearch
time_format: decade
query_variants:
  - V1_TOPIC_COUNTRY_TIME_ALL_TOPICS
```

Run after each change:

```bash
python -m src.generate_queries --config config.yaml
python -m src.run_llm --config config.yaml
python -m src.match_and_eval --config config.yaml
```

Expanded comparison setup:

```yaml
input_path: random_100_datasets_full_metadata.csv
qrels_input_path: all_research_data_full_metadata.csv
output_dir: output/full_metadata_model_comparison
query_variants:
  - V2_TOPIC_COUNTRY_TIME_SINGLE_TOPIC
modes:
  - NO_WEB
  - WEB_SEARCH
models_no_web:
  - gpt-5.1
models_web:
  - gpt-5.1
```

This generates queries from the 100-row sample but builds qrels and matches returned datasets against the full metadata file.
<!--
## OpenWebUI Prerequisites

If you use OpenWebUI and want real `WEB_SEARCH`, configure OpenWebUI first:

- Enable Web Search globally in Admin Panel -> Settings -> Web Search.
- Configure a search provider such as SearXNG, Tavily, SearchApi, or another supported engine.
- Ensure the model selected by `model_web` has the Web Search capability enabled in OpenWebUI.
- If you want agentic search with tool use, set that model's Function Calling mode to `Native`.

If you want to use the OpenAI hosted API instead of OpenWebUI, set `api_base_url` to empty and set `api_key_env: OPENAI_API_KEY`, then export `OPENAI_API_KEY`.
-->
