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

Set the API key for the provider configured in `config.yaml`. For OpenAI API runs, use `OPENAI_API_KEY`; for GESIS OpenWebUI runs, use `OPENWEBUI_API_KEY`.

PowerShell:

```powershell
$env:OPENAI_API_KEY = "YOUR_OPENAI_KEY"
$env:OPENWEBUI_API_KEY = "YOUR_KEY"
$env:GEMINI_API_KEY = "YOUR_GEMINI_KEY"
```

Linux:

```bash
export OPENAI_API_KEY='YOUR_OPENAI_KEY'
export OPENWEBUI_API_KEY='YOUR_KEY'
export GEMINI_API_KEY='YOUR_GEMINI_KEY'
```

The full metadata file is not stored in Git. Place `all_research_data_full_metadata.csv` in the repository root or update `qrels_input_path` in `config.yaml`.

## Gemini Web Search Run

`config_gemini_websearch.yaml` runs Gemini with Google Search grounding for the 100-dataset sample. It uses `gemini-3.6-flash`, `WEB_SEARCH` only, no returned-item threshold in the prompt, and saves all returned items.

```bash
python -m src.generate_queries --config config_gemini_websearch.yaml -V V1
python -m src.run_llm --config config_gemini_websearch.yaml -V V1
python -m src.match_and_eval --config config_gemini_websearch.yaml -V V1
python -m src.audit_results --config config_gemini_websearch.yaml -V V1
```

Gemini web search is implemented as a separate provider path because OpenAI web search uses OpenAI's Responses API tools, while Gemini uses Google Search grounding.

## Configuration

The main settings are in `config.yaml`:

- `input_path`: sample metadata used to generate queries.
- `qrels_input_path`: metadata corpus used to build qrels and match returned datasets.
- `source_row_limit`: maximum number of source metadata rows used during query generation.
- `query_variants`: active query variant. Use one variant per run for separate outputs.
- `time_format`: `years`, `span`, or `decade`.
- `modes`: `NO_WEB`, `WEB_SEARCH`, or both.
- `models_no_web` and `models_web`: models evaluated in each mode.
- `top_k_return`: evaluation cutoff used for @k metrics.
- `include_top_k_limit_in_prompt`: when `false`, the prompt does not ask for a maximum number of items.
- `max_returned_items_to_save`: maximum number of returned items saved from each model response; `0` saves all returned items.
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
  V6_TOPIC_COUNTRY_TIME_ABSTRACT_NATURAL_LANGUAGE: output/full_metadata_model_comparison/v6_all_topics_abstract_natural_language
```

When exactly one variant is active, every pipeline stage uses its mapped output directory. If multiple variants are active, the general `output_dir` is used.

## Query Variants

- `V1_TOPIC_COUNTRY_TIME_ALL_TOPICS`: one query per source dataset using all topics, countries, and time.
- `V2_TOPIC_COUNTRY_TIME_SINGLE_TOPIC`: one query for each individual topic, with the same countries and time.
- `V3_TITLE_ONLY`: one known-item query using the dataset title.
- `V4_TOPIC_COUNTRY_TIME_UNIVERSE_ANALYSIS_UNIT_ALL_TOPICS`: extends V1 with the study population (`universe_en`) and unit of analysis (`analysis_unit_en`). A query is generated only when both fields contain meaningful values.
- `V5_TOPIC_COUNTRY_TIME_UNIVERSE_ALL_TOPICS`: extends V1 with only the study population (`universe_en`). A query is generated when the universe contains a meaningful value; analysis unit is not used.
- `V6_TOPIC_COUNTRY_TIME_ABSTRACT_NATURAL_LANGUAGE`: extends V1 with a natural-language research need generated from the dataset abstract. A fixed query-generation model rewrites the abstract once; the generated text is saved in `queries.csv` and cached in `abstract_query_cache.csv`, so later model comparisons use the same query text.

Current templates:

```text
Can you find datasets about {topic} in {country} during the {time}?
Can you find the dataset titled {title}?
Can you find datasets about {topic} in {country} during the {time}, where the study population is {universe} and the unit of analysis is {analysis_unit}?
Can you find datasets about {topic} in {country} during the {time}, where the study population is {universe}?
Can you find datasets about {topic} in {country} during the {time}, matching this research need: {abstract_generated_query}
```

Prompt values are formatted as natural text. The structured topic, country, and exact year values remain in separate `queries.csv` columns for qrels construction.

For V4, `query_universe` and `query_analysis_units` are also stored separately. With `qrels_strategy: metadata_filter`, a relevant dataset must match the normal V1 criteria and both added fields. The current 100-dataset sample contains 21 rows eligible for this variant when English fields and German fallbacks are considered.

For V5, only `query_universe` is added to the normal V1 criteria. Analysis unit is neither included in the prompt nor required by the metadata-filter qrels. The current sample contains 80 eligible source rows before duplicate query removal.

For V6, set `abstract_query_generator_model` in `config.yaml` to the fixed model used to create the natural-language query text. The generator can use separate provider settings via `abstract_query_generator_api_base_url` and `abstract_query_generator_api_key_env`, so abstract-query generation can use GESIS OpenWebUI while the discovery run uses OpenAI. The generated query is stored in `abstract_generated_query`; the final API prompt is stored in `full_prompt_no_web` and `full_prompt_web_search`. With `qrels_strategy: metadata_filter`, V6 uses the same topic, country, and time relevance logic as V1.

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

Aliases `V1`, `V2`, `V3`, `V4`, `V5`, and `V6` resolve to their full variant names and select the corresponding directory from `output_dir_by_variant`. The command-line override does not modify `config.yaml`.

To run all variants sequentially while keeping separate output folders, use the PowerShell runner:

```powershell
.\run_all_variants.ps1
```

It runs `generate_queries`, `run_llm`, `match_and_eval`, and `audit_results` for `V1` through `V6`, using the `output_dir_by_variant` mapping. A transcript is written to `output/full_metadata_model_comparison/run_all_variants_<timestamp>.log`.

You can restrict the variants:

```powershell
.\run_all_variants.ps1 -Variants V1,V2,V3
```

Or stop immediately if one stage fails:

```powershell
.\run_all_variants.ps1 -StopOnError
```

On Linux, use the Bash runner:

```bash
bash run_all_variants.sh
```

Restrict variants on Linux with a comma-separated list:

```bash
bash run_all_variants.sh --variants V1,V2,V3
```

Run `generate_queries` again whenever the query variant, source row limit, time format, or input sample changes. Changing `source_row_limit` does not modify an existing `queries.csv` automatically.

For a model or mode comparison, keep the generated queries fixed and change only the configured model lists or modes.

If the goal is to test whether a dataset is found regardless of its position, use:

```yaml
include_top_k_limit_in_prompt: false
max_returned_items_to_save: 0
```

Then inspect the returned `rank` in `llm_results.csv` / `per_query_results.csv`. The prompt and saved model outputs do not impose a returned-item threshold. The @k metrics still use `top_k_return` as the reporting cutoff for comparability.

## Stage Responsibilities

### 1. Generate Queries

`src.generate_queries` reads the sample metadata and writes `queries.csv`. In addition to `query_text`, it stores `full_prompt_no_web` and `full_prompt_web_search`, including the system instruction and required JSON format. If `include_top_k_limit_in_prompt: false`, the stored prompt has no returned-item threshold. The number of queries can exceed the number of source datasets for the single-topic variant because one dataset can have several topics.

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
- `hit_at_k_all_queries`: proportion of all requests with at least one relevant dataset within the evaluation cutoff `top_k_return`.
- `mrr_all_queries`: rewards placing the first relevant dataset near the top.
- `ndcg_at_k_all_queries`: evaluates the ranking of one or more relevant datasets within the evaluation cutoff `top_k_return`.
- `strict_hit_at_k_all_queries`: proportion of all requests with at least one relevant dataset matched through a DOI, known landing-page URL, or dataset ID.
- `title_match_hit_at_k_all_queries`: proportion of all requests where relevance was credited only through title matching.
- `exact_hit_at_k_all_queries`: legacy-compatible strict hit rate based on DOI, URL, or dataset ID matching.
- `fuzzy_hit_at_k_all_queries`: legacy-compatible title-match hit rate.

`is_gesis_relevant_dataset` in `per_query_results.csv` is the broad qrels-based GESIS relevance flag. It can be true for identifier or title-based matches. For reporting valid dataset discovery, prefer `is_strict_gesis_relevant_dataset`, `is_strict_source_dataset`, and the strict metrics. `match_method` shows the primary match method: `doi`, `portal_url`, `dataset_id`, `title_exact`, `title_fuzzy`, or `unmatched`.

For broad discovery variants such as V1 and V6, the evaluation separates the original sampled dataset from other matching GESIS datasets:

- `is_source_dataset` / `source_hit_at_k`: the returned item matches the original sampled source dataset.
- `is_gesis_relevant_dataset` / `gesis_relevant_hit_at_k`: the returned item is a GESIS dataset in the metadata corpus and is relevant according to the query qrels.
- `is_strict_source_dataset` and `is_strict_gesis_relevant_dataset`: the match is supported by DOI, URL, or dataset ID.
- `is_title_source_dataset` and `is_title_gesis_relevant_dataset`: the match is based on title matching rather than a reliable identifier.

The latest report in `reports/model_comparison/` first uses V1/V6 to compare providers, then continues with OpenAI only to compare V1, V2, and V6. The provider comparison in `provider_strict_source_gesis_summary.csv` uses the strict source and strict GESIS metrics:

| Variant | Provider | Strict Source Hits | Hit Value | Strict GESIS Hits | Hit Value |
| --- | --- | ---: | ---: | ---: | ---: |
| V1 | OpenAI | 6 / 85 | 0.071 | 21 / 85 | 0.247 |
| V1 | OpenWebUI | 0 / 78 | 0.000 | 10 / 78 | 0.128 |
| V6 | OpenAI | 23 / 87 | 0.264 | 37 / 87 | 0.425 |
| V6 | OpenWebUI | 0 / 85 | 0.000 | 13 / 85 | 0.153 |

`Strict Source Hits` means the original sampled dataset was found through DOI, landing-page URL, or dataset ID. `Strict GESIS Hits` means any qrels-relevant GESIS dataset was found through DOI, landing-page URL, or dataset ID.

Precision@k is available but should not be the main title-search metric because a known-item query normally has one target while the denominator remains `k`.

## Reports

The curated current comparison is under `reports/model_comparison/`:

- `INTERPRETATION.md`: concise provider-check and OpenAI variant-comparison interpretation.
- `provider_strict_source_gesis_summary.csv`: compact OpenAI/OpenWebUI strict source/GESIS hit table for V1/V6.
- `openai_variant_comparison_summary.csv`: compact OpenAI-only comparison for V1/V2/V6.
- `v1_queries.csv`, `v2_queries.csv`, and `v6_queries.csv`: prompts used in the current experiment.
- `v1_provider_difference_summary.csv` and `v6_provider_difference_summary.csv`: OpenAI/OpenWebUI query-level comparison summaries.
- `v1_provider_differences.csv` and `v6_provider_differences.csv`: per-query provider comparison.
- `v1_provider_outputs_query_level.csv` and `v6_provider_outputs_query_level.csv`: selected query-level outputs from both providers.

Start with `reports/model_comparison/INTERPRETATION.md`, then use the CSV files to inspect individual models, queries, and returned datasets.

## OpenWebUI Notes

For `WEB_SEARCH`, the current OpenWebUI configuration uses the native chat-completions endpoint and `openwebui_web_search_mode: tool_ids`. Web search must also be enabled for the selected model on the OpenWebUI server.

A successful HTTP response is not sufficient: a model can return a tool call without a final answer. These cases are visible in the raw logs and are counted separately by `audit_results`. By default the pipeline sends `tool_choice: "none"` (`openwebui_tool_choice`) so models answer directly instead of calling OpenWebUI's workspace tools; see [Why `tool_choice: "none"`](#why-tool_choice-none) below.

### Why `tool_choice: "none"`

The GESIS OpenWebUI server binds workspace tools (`search_knowledge_files`, `query_knowledge_files`, `search_knowledge_bases`, `search_notes`, `search_chats`) to some model configurations. These search the user's uploaded documents, notes, and chat history — not the GESIS dataset catalog. Reasoning models such as `gpt-5` and `gpt-5.4` call these tools instead of answering, returning `content: null` with `finish_reason: tool_calls`, so they never produce a usable result. Sending `tool_choice: "none"` forbids these calls and forces a direct answer; it does not disable server-side web search, which OpenWebUI injects into the prompt rather than exposing as a model-called tool. Suppressing the workspace tools also keeps the comparison fair: every model answers from its own knowledge (plus web search when enabled) under identical conditions, rather than being influenced by whatever happens to be in a given workspace.
