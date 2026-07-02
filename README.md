# LLM-Mediated Findability of GESIS Datasets

This repository evaluates how well language models discover and rank GESIS datasets. Test queries are generated from a 100-dataset sample, while relevant datasets and returned records can be matched against the full GESIS metadata collection.

## Pipeline

The pipeline has four stages:

```text
metadata sample
      |
      v
generate_queries -> queries.csv
      |
      v
run_llm -> llm_results.csv + request/response logs
      |
      v
match_and_eval -> qrels + relevance labels + answered-query metrics
      |
      v
audit_results -> coverage-aware model comparison metrics
```

The stages remain separate so query generation, API calls, matching, and auditing can be inspected independently.

## Setup

Create and activate an environment, then install the dependencies:

```bash
conda create -n gesis-findability python=3.11
conda activate gesis-findability
pip install -r requirements.txt
```

Set the OpenWebUI API key.

PowerShell:

```powershell
$env:OPENWEBUI_API_KEY = "YOUR_KEY"
```

Linux:

```bash
export OPENWEBUI_API_KEY='YOUR_KEY'
```

The full metadata file is not stored in Git. Place `all_research_data_full_metadata.csv` in the repository root or update `qrels_input_path` in `config.yaml`.

## Configuration

The main settings are in `config.yaml`:

- `input_path`: sample metadata used to generate queries.
- `qrels_input_path`: metadata corpus used to build qrels and match returned datasets.
- `source_row_limit`: maximum number of source metadata rows used during query generation.
- `query_variants`: active query variant. Use one variant per run for separate outputs.
- `time_format`: `years`, `span`, or `decade`.
- `modes`: `NO_WEB`, `WEB_SEARCH`, or both.
- `models_no_web` and `models_web`: models evaluated in each mode.
- `top_k_return`: maximum number of datasets requested from each model.
- `qrels_strategy`: relevance strategy; the current comparison uses `metadata_filter`.
- `output_dir_by_variant`: output directory selected for each single active variant.
- `api_base_url`, `api_key_env`, and `openwebui_web_search_mode`: OpenWebUI connection settings.
- `openwebui_tool_choice`: controls tool calling for OpenWebUI models. Defaults to `none`, which forbids the model from calling OpenWebUI's server-injected workspace tools (see OpenWebUI Notes). Set to `auto` to restore the previous behavior.
- `request_timeout_*` and `request_max_retries`: request timeout and retry settings.

Example:

```yaml
input_path: random_100_datasets_full_metadata.csv
qrels_input_path: all_research_data_full_metadata.csv
source_row_limit: 100
time_format: decade
query_variants:
  - V2_TOPIC_COUNTRY_TIME_SINGLE_TOPIC
modes:
  - NO_WEB
  - WEB_SEARCH
output_dir_by_variant:
  V1_TOPIC_COUNTRY_TIME_ALL_TOPICS: output/full_metadata_model_comparison/v1_all_topics
  V2_TOPIC_COUNTRY_TIME_SINGLE_TOPIC: output/full_metadata_model_comparison/v2_single_topic
  V3_TITLE_ONLY: output/full_metadata_model_comparison/v3_title_only
  V4_TOPIC_COUNTRY_TIME_UNIVERSE_ANALYSIS_UNIT_ALL_TOPICS: output/full_metadata_model_comparison/v4_all_topics_population_unit
  V5_TOPIC_COUNTRY_TIME_UNIVERSE_ALL_TOPICS: output/full_metadata_model_comparison/v5_all_topics_population
```

When exactly one variant is active, every pipeline stage uses its mapped output directory. If multiple variants are active, the general `output_dir` is used.

## Query Variants

- `V1_TOPIC_COUNTRY_TIME_ALL_TOPICS`: one query per source dataset using all topics, countries, and time.
- `V2_TOPIC_COUNTRY_TIME_SINGLE_TOPIC`: one query for each individual topic, with the same countries and time.
- `V3_TITLE_ONLY`: one known-item query using the dataset title.
- `V4_TOPIC_COUNTRY_TIME_UNIVERSE_ANALYSIS_UNIT_ALL_TOPICS`: extends V1 with the study population (`universe_en`) and unit of analysis (`analysis_unit_en`). A query is generated only when both fields contain meaningful values.
- `V5_TOPIC_COUNTRY_TIME_UNIVERSE_ALL_TOPICS`: extends V1 with only the study population (`universe_en`). A query is generated when the universe contains a meaningful value; analysis unit is not used.

Current templates:

```text
Can you find GESIS datasets about {topic} in {country} during the {time}?
Can you find the GESIS dataset titled {title}?
Can you find GESIS datasets about {topic} in {country} during the {time}, where the study population is {universe} and the unit of analysis is {analysis_unit}?
Can you find GESIS datasets about {topic} in {country} during the {time}, where the study population is {universe}?
```

Prompt values are formatted as natural text. The structured topic, country, and exact year values remain in separate `queries.csv` columns for qrels construction.

For V4, `query_universe` and `query_analysis_units` are also stored separately. With `qrels_strategy: metadata_filter`, a relevant dataset must match the normal V1 criteria and both added fields. The current 100-dataset sample contains 21 rows eligible for this variant when English fields and German fallbacks are considered.

For V5, only `query_universe` is added to the normal V1 criteria. Analysis unit is neither included in the prompt nor required by the metadata-filter qrels. The current sample contains 80 eligible source rows before duplicate query removal.

## Run the Pipeline

After selecting one query variant and the required models in `config.yaml`, run:

```bash
python -m src.generate_queries --config config.yaml
python -m src.run_llm --config config.yaml
python -m src.match_and_eval --config config.yaml
python -m src.audit_results --config config.yaml
```

You can override the configured variant for any stage without editing `config.yaml`. Use the same variant for all four commands:

```bash
python -m src.generate_queries --config config.yaml --variant V1
python -m src.run_llm --config config.yaml --variant V1
python -m src.match_and_eval --config config.yaml --variant V1
python -m src.audit_results --config config.yaml --variant V1
```

The short form is also supported:

```bash
python -m src.generate_queries -V V1 --config config.yaml
```

Aliases `V1`, `V2`, `V3`, `V4`, and `V5` resolve to their full variant names and select the corresponding directory from `output_dir_by_variant`. The command-line override does not modify `config.yaml`.

Run `generate_queries` again whenever the query variant, source row limit, time format, or input sample changes. Changing `source_row_limit` does not modify an existing `queries.csv` automatically.

For a model or mode comparison, keep the generated queries fixed and change only the configured model lists or modes.

## Stage Responsibilities

### 1. Generate Queries

`src.generate_queries` reads the sample metadata and writes `queries.csv`. In addition to `query_text`, it stores `full_prompt_no_web` and `full_prompt_web_search`, including the system instruction, top-k limit, and required JSON format. The number of queries can exceed the number of source datasets for the single-topic variant because one dataset can have several topics.

### 2. Query Models

`src.run_llm` sends every query to each configured model and mode. It writes normalized ranked items to `llm_results.csv` and stores the complete message list and API response for every attempt under `logs/` in the selected output directory. Authorization headers and API keys are not logged.

### 3. Match and Evaluate

`src.match_and_eval`:

- builds `qrels.csv` from the evaluation metadata;
- matches returned IDs, DOIs, URLs, and titles to metadata records;
- labels returned items in `per_query_results.csv`;
- calculates per-query and answered-query summary metrics.

Its summary may omit requests that produced no usable returned items.

### 4. Audit Results

`src.audit_results` checks every expected query, model, and mode combination against the logs and evaluation output. Empty, missing, error, and unfinished tool-call responses count as zero. Use `metrics_summary_audit.csv` for the fairest model comparison.

## Output Files

Each variant output directory contains:

- `queries.csv`: generated query text, complete initial prompts for both modes, and source metadata.
- `llm_results.csv`: normalized datasets returned by models.
- `logs/`: request messages, responses, retries, and tool-call states.
- `qrels.csv`: datasets considered relevant to each query.
- `qrels_debug.csv`: metadata-filter matching diagnostics, when enabled.
- `per_query_results.csv`: returned items with metadata matches and relevance labels.
- `metrics_per_query.csv`: metrics for requests with evaluation rows.
- `metrics_summary.csv`: answered-query summary from `match_and_eval`.
- `metrics_audit_per_request.csv`: one audit row for every expected request.
- `metrics_summary_audit.csv`: coverage-aware model comparison summary.
- `metrics_response_status_audit.csv`: counts of usable, empty, missing, error, and tool-only responses.

Pipeline CSV files use a semicolon (`;`) separator for compatibility with German and European Excel settings. Readers also accept older comma-separated files.

## Main Metrics

- `coverage_rate`: proportion of all requests that returned at least one usable item.
- `hit_at_k_all_queries`: proportion of all requests with at least one relevant dataset in the top-k results.
- `mrr_all_queries`: rewards placing the first relevant dataset near the top.
- `ndcg_at_k_all_queries`: evaluates the ranking of one or more relevant datasets in the top-k results.
- `exact_hit_at_k_all_queries`: hits matched through an exact identifier, DOI, URL, or equivalent exact match.
- `fuzzy_hit_at_k_all_queries`: hits credited through fuzzy title matching only.

Precision@k is available but should not be the main title-search metric because a known-item query normally has one target while the denominator remains `k`.

## Reports

The curated comparison is under `reports/model_comparison/`:

- `INTERPRETATION.md`: consolidated study design, results, and interpretation.
- `*_summary.csv`: coverage-aware model comparisons by query variant.
- `*_response_status.csv`: response diagnostics.
- `*_queries.csv`: prompts used in each experiment.
- `*_model_outputs_top10_labeled.csv`: returned top-10 items with matches and relevance labels.

Start with `reports/model_comparison/INTERPRETATION.md`, then use the CSV files to inspect individual models, queries, and returned datasets.

## OpenWebUI Notes

For `WEB_SEARCH`, the current OpenWebUI configuration uses the native chat-completions endpoint and `openwebui_web_search_mode: tool_ids`. Web search must also be enabled for the selected model on the OpenWebUI server.

A successful HTTP response is not sufficient: a model can return a tool call without a final answer. These cases are visible in the raw logs and are counted separately by `audit_results`. By default the pipeline sends `tool_choice: "none"` (`openwebui_tool_choice`) so models answer directly instead of calling OpenWebUI's workspace tools; see [Why `tool_choice: "none"`](#why-tool_choice-none) below.

### Why `tool_choice: "none"`

The GESIS OpenWebUI server binds workspace tools (`search_knowledge_files`, `query_knowledge_files`, `search_knowledge_bases`, `search_notes`, `search_chats`) to some model configurations. These search the user's uploaded documents, notes, and chat history — not the GESIS dataset catalog. Reasoning models such as `gpt-5` and `gpt-5.4` call these tools instead of answering, returning `content: null` with `finish_reason: tool_calls`, so they never produce a usable result. Sending `tool_choice: "none"` forbids these calls and forces a direct answer; it does not disable server-side web search, which OpenWebUI injects into the prompt rather than exposing as a model-called tool. Suppressing the workspace tools also keeps the comparison fair: every model answers from its own knowledge (plus web search when enabled) under identical conditions, rather than being influenced by whatever happens to be in a given workspace.
