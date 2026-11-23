# LLM-Mediated Findability of GESIS Datasets

This repository evaluates how well language models discover and rank GESIS datasets. Test queries are generated from a 100-dataset sample, while relevant datasets and returned records can be matched against the full GESIS metadata collection.

## Pipeline

### Optional Versus Required OpenAI Search

To prepare a complete required-search OpenAI rerun for both saved samples
(random-100 and top-10, V1/V2/V3/V6), without regenerating prompts:

```powershell
python -m scripts.run_openai_required
```

This creates a new folder under `output/openai_required_websearch/`, validates
saved full prompts against the current message builder, and copies query CSVs
byte-for-byte. It prints a command with `--run-dir ... --execute` to submit the
610 planned requests and run evaluation/audit. Preparation alone uses no API.
The original results and report tables are not replaced. An execution refuses
to overwrite existing `llm_results.csv` files; partial runs require inspection
before continuing. Retries can add API requests beyond the planned count.

The original OpenAI `WEB_SEARCH` runs made search available without requiring a
tool call. A paired investigation reuses six historical empty V3 prompts (IDs
18, 22, 53, 69, 72, 94) with `tool_choice=auto` versus `required`.
Only the web-search tool is available in these requests. The existing default
remains `auto`; other providers and existing experiment files are unchanged.

Prepare the comparison without making API calls:

```powershell
python -m src.compare_search_modes
```

Execute a new comparison after setting `OPENAI_API_KEY`:

```powershell
python -m src.compare_search_modes --execute --repeats 3
```

This schedules 36 requests (six prompts, two conditions, three repetitions),
plus any retries. `--repeats 1` schedules 12 requests for an initial check.
`--model` selects one model for both conditions; otherwise the OpenAI profile's
model is used. Query text and complete prompts are checked against the saved
original wording. Prompt order is shuffled identically within each pair and
condition order alternates across repetitions. Each condition has separate
logs, CSVs and a resolved configuration under a unique
`output/search_mode_comparison/<comparison-id>/` folder.

The command evaluates and audits each condition, then writes
`comparison_per_request.csv` and `comparison_summary.csv`. These report actual
search actions, empty answers, API errors, strict source hits, evaluation
availability and the model name returned by the API. Rebuild those summaries
without API calls with:

```powershell
python -m src.compare_search_modes --summarize output/search_mode_comparison/<comparison-id>
```

This is a diagnostic on selected failures, not an estimate of all-dataset
performance. Compare the contemporaneous conditions; changing model aliases,
index contents and dates prevent treating differences from historical runs as
caused only by required search. A successful tool call does not itself prove
that useful results or correct dataset identifiers were found. Incomplete runs
have missing logs or unevaluated requests and should not be interpreted as a
completed comparison. Each `--execute` invocation starts a new comparison.

### Local Web Interface

The Streamlit interface uses the same generation, retrieval, evaluation and audit
stages as the command line. Install the optional web dependencies in the active
environment and start it from the repository root:

```powershell
conda activate gesis-findability
python -m pip install -r requirements-web.txt
python -m streamlit run app.py
```

Open `http://127.0.0.1:8501`. The default configuration binds to this computer
only. Set provider API keys in the terminal before starting the server; keys are
read from environment variables and are not entered into the interface.

The **Experiments** view opens existing runs under `output/experiments/`, with
coverage and matching metrics, returned dataset evidence, full prompts and CSV
downloads. Filter returned items by query, strict source match, relevance,
identifier conflict or explicit failure. Repository attribution remains a model
claim; catalogue matches do not independently validate a live URL.

Use **New experiment** to select OpenAI, Gemini or OpenWebUI; a metadata preset
or supported metadata combination; the random100/top10 source profile or an
uploaded metadata CSV; a model; and a source row limit. All interface runs use
`WEB_SEARCH`. Uploaded files must use
the existing metadata schema and are saved by content hash under
`output/web_uploads/`. Evaluation still uses the full corpus configured in
`experiment.yaml`. **Sample data and metadata columns** shows the source fields
and previews selected records. The row limit takes the first rows of the saved
sample; it does not draw a new random sample.

**Metadata fields** determines the evaluation variant automatically:

| Selected metadata | Topics per query | Variant |
| --- | --- | --- |
| Title | Not applicable | V3 |
| Topic, country, collection time | All topics | V1 |
| Topic, country, collection time | Single topic | V2 |
| Topic, country, collection time, population | All topics | V5 |
| Topic, country, collection time, population, analysis unit | All topics | V4 |
| Topic, country, collection time, abstract-derived research need | All topics | V6 |

Unsupported combinations cannot start a run: they need explicit generation and
relevance rules first. V6's automated relevance reference still uses topic,
country and time; abstract-specific relevance is not independently assessed.
The selected fields and named template are saved with each run. Source-column
labels show the standard loader's English-first fallbacks, not a custom mapping.

**Prompt template** lists only compatible named templates from `experiment.yaml`.
Choose search/download wording where available, then edit it if needed. Templates
are editable with validated placeholders:

- V3: `{title}`.
- V1/V2: `{topic}`, `{country}`, `{time_collection_years}`.
- V5: the V1 placeholders plus `{universe}`.
- V4: the V5 placeholders plus `{analysis_unit}`.
- V6: the V1 placeholders plus `{abstract_query}`.

**Preview prompts** is offline. It uses the same query builder and shared V6
cache; uncached abstract queries are reported and omitted from the preview.
**Generate prompts** creates a saved run without retrieval. V6 generation may
call the configured abstract model for missing cache entries. **Start experiment**
runs the complete pipeline and consumes provider quota. Every run stores its
resolved settings, source fingerprints and stage history.

Jobs run in a background process and survive a browser refresh or navigation.
Keep the computer/server running. The run view refreshes status every three
seconds, exposes execution logs and supports stopping the current job.
**Run retrieval & evaluation** continues a prompt-only run (or repeats retrieval,
replacing that run's responses); **Re-evaluate saved responses** only runs matching
and audit without model calls. Run the interface on the same machine that owns
the paths saved in `resolved_config.yaml`.

### Unified Experiment Command

New experiments use `experiment.yaml`, which defines shared settings, dataset
profiles, provider defaults, and named title templates. Existing configurations
and individual stage commands remain supported.

Run the 100-dataset Gemini experiment with the download title prompt:

```powershell
python -m src.run_pipeline --provider gemini --sample random100 -V V3 --template title_download
```

Other examples:

```powershell
python -m src.run_pipeline --provider openai --sample top10 -V V1
python -m src.run_pipeline --provider gemini --sample random100 -V V6
python -m src.run_pipeline --provider openai --sample random100 -V V2 --limit 3
```

The mode defaults to `WEB_SEARCH`. Set `--model` to override the provider's
default model. `--template title_original` and `--template title_download` are
V3 templates; other variants use their established generation logic. The
`default` template preserves existing prompts. V6 uses the same shared abstract
query cache for both providers, with separate caches for random100 and top10.
Uncached V6 generation needs `OPENWEBUI_API_KEY` for its fixed generator.

Use `--input-path` and `--qrels-input-path` for custom metadata files.
`--limit` limits source rows, not returned items; zero uses all input rows.
No result limit is added to prompts, and all returned items are saved.
`top_k_return: 10` remains the evaluation cutoff.

Preview without writing files or making API calls:

```powershell
python -m src.run_pipeline --provider gemini -V V3 --template title_download --dry-run
```

Every new run creates a unique directory under `output/experiments/`, containing
the existing CSV results and request logs, `resolved_config.yaml`, an
`experiment.json` manifest with input SHA-256 fingerprints, and a `stages.jsonl`
execution history. API keys stay in environment variables. Command-line
selections override profiles; each run keeps its resolved settings.

Generate prompts without running retrieval:

```powershell
python -m src.run_pipeline --provider gemini -V V3 --template title_download --stages generate_queries
```

Continue that run, using the directory printed by the command:

```powershell
python -m src.run_pipeline --run-dir output/experiments/<run-directory> --stages run_llm match_and_eval audit_results
```

Re-evaluate saved responses without API calls:

```powershell
python -m src.run_pipeline --run-dir output/experiments/<run-directory> --stages match_and_eval audit_results
```

Resume uses the saved configuration and rejects experiment overrides. Selecting
`run_llm` explicitly calls the API again and replaces that run's retrieval results.
Execution stops at the first failed stage. Existing results and older configuration
files are retained during migration.

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

### Response Evidence and Repository Attribution

The metadata loader preserves original, English, study and alternative title
fields for evaluation. The primary `title` remains English-first for query
generation. Returned German titles can therefore match the same dataset without
requiring translation or changing generated prompts. The `title_match_column`
field records which title field supported the match.

Evaluation uses the same response rules for V1, V2, V3 and V6, for every provider.
An item with no returned link and an explicit failed-search statement is flagged
`reports_not_found_without_link=1`. It receives no source or relevance hit,
including title-based hits. Raw title matches remain available in
`title_matched_dataset_id`, `title_match_score` and `title_match_method`.
Positive title matches are diagnostic evidence, not proof of a working dataset
link. Strict identifier metrics continue to use catalogue identifiers, DOIs and
record URLs; they do not perform live webpage verification.

`per_query_results.csv` also records:

- `repository_mentions`: repository names occurring in the model's justification.
- `claimed_data_providers`: positive provider attribution extracted from the text.
- `claimed_catalogues`: positive catalogue attribution, with CESSDA distinguished
  from the data provider.
- `returned_link_repository`: recognized domain of the returned URL. DOI links
  remain unresolved here; their registrant is not inferred from the DOI domain.
- `repository_attribution_status`: `positive_claim` or `unresolved`.

These are conservative English-language rules, not verified repository ownership
or a general natural-language inference engine. Negative or ambiguous sentences
are left unresolved; a missing extracted claim is not evidence that the provider
was wrong. A GESIS mention in a failed search is not a positive attribution.
Correct attribution rates require validation against authoritative repository
metadata or reviewed labels; the automatic outputs report model claims only.

After evaluation, audit writes `repository_attribution_per_query.csv` and
`repository_attribution_summary.csv`. Mention and attribution-claim rates use
all configured requests as their denominator and all saved returned items as
evidence, independently of the ranking cutoff. An item containing a failure does
not invalidate other successful items for the same query.

Re-running evaluation and audit on saved responses updates these outputs without
calling a model. Existing reports are not automatically regenerated.

## Setup

Create and activate an environment, then install the dependencies:

```bash
conda create -n gesis-findability python=3.11
conda activate gesis-findability
pip install -r requirements.txt
```

Set the API key for the provider configured in the run config. For OpenAI API runs, use `OPENAI_API_KEY`; for GESIS OpenWebUI runs, use `OPENWEBUI_API_KEY`; for Gemini runs, use `GEMINI_API_KEY`.

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

The current Gemini comparison uses V1, V2, V3, and V6. After rerunning transient failures, V1, V2, and V3 have high or full item coverage. V3 has two Gemini API errors; V6 has one Gemini API error and one valid empty-item response.

## Top-10 Popular Dataset Visibility Run

The top-10 visibility check uses popular/requested datasets as the query source and the full GESIS metadata file as the evaluation corpus. This is useful for testing whether frequently used datasets are more visible to LLM-mediated search than the random sample.

Available configs:

- `config_top10_requested_openai.yaml`: OpenAI API web search over `top 10/requested_10_datasets_full_metadata.csv`.
- `config_top10_logs_openai.yaml`: OpenAI API web search over `top 10/top_10_from_logs.csv`.
- `config_top10_requested_gemini.yaml`: Gemini web search over `top 10/requested_10_datasets_full_metadata.csv`.
- `config_top10_logs_gemini.yaml`: Gemini web search over `top 10/top_10_from_logs.csv`.

Run V1, V2, and V3 together for the requested/downloaded top-10 list. Use the OpenAI or Gemini config depending on the provider:

```powershell
.\run_all_variants.ps1 `
  -Config config_top10_requested_openai.yaml `
  -Variants V1,V2,V3 `
  -StopOnError

.\run_all_variants.ps1 `
  -Config config_top10_requested_gemini.yaml `
  -Variants V1,V2,V3 `
  -StopOnError
```

Run V6 separately if abstract-generated queries are needed:

```powershell
.\run_all_variants.ps1 `
  -Config config_top10_requested_openai.yaml `
  -Variants V6 `
  -StopOnError

.\run_all_variants.ps1 `
  -Config config_top10_requested_gemini.yaml `
  -Variants V6 `
  -StopOnError
```

Run link-quality audits after title or abstract-based runs:

```powershell
python -m src.audit_links --config config_top10_requested_openai.yaml -V V3
python -m src.audit_links --config config_top10_requested_openai.yaml -V V6
python -m src.audit_links --config config_top10_requested_gemini.yaml -V V3
python -m src.audit_links --config config_top10_requested_gemini.yaml -V V6
```

Top-10 outputs are written under:

```text
output/top10_visibility/requested_openai/
output/top10_visibility/logs_openai/
output/top10_visibility/requested_gemini/
output/top10_visibility/logs_gemini/
```

Curated top-10 OpenAI/Gemini summaries for reporting are stored in `reports/model_comparison/`:

- `top10_provider_variant_summary.csv`
- `top10_provider_response_status.csv`
- `top10_provider_queries.csv`
- `top10_provider_outputs_labeled.csv`
- `top10_provider_link_audit_summary.csv`
- `top10_provider_title_identifier_conflicts.csv`

Refresh these combined files after rerunning top-10 evaluation and audit:

```bash
python -m src.build_top10_report
```

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
- `abstract_query_cache_path`: shared V6 natural-query cache. Use the same path across provider configs to guarantee identical abstract-derived query text.
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

The latest report in `reports/model_comparison/` uses V1/V3/V6 for provider context and compares OpenAI and Gemini across V1, V2, V3, and V6. The provider comparison in `provider_strict_source_gesis_summary.csv` uses the strict source and strict GESIS metrics:

| Variant | Provider | Strict Source Hits | Hit Value | Strict GESIS Hits | Hit Value |
| --- | --- | ---: | ---: | ---: | ---: |
| V1 | OpenAI | 7 / 85 | 0.082 | 21 / 85 | 0.247 |
| V1 | OpenWebUI | 0 / 85 | 0.000 | 10 / 85 | 0.118 |
| V1 | Gemini | 1 / 85 | 0.012 | 18 / 85 | 0.212 |
| V3 | OpenAI | 37 / 100 | 0.370 | 37 / 100 | 0.370 |
| V3 | Gemini | 64 / 100 | 0.640 | 64 / 100 | 0.640 |
| V6 | OpenAI | 23 / 87 | 0.264 | 37 / 87 | 0.425 |
| V6 | OpenWebUI | 0 / 87 | 0.000 | 12 / 87 | 0.138 |
| V6 | Gemini | 28 / 87 | 0.322 | 37 / 87 | 0.425 |

`Strict Source Hits` means the original sampled dataset was found through DOI, landing-page URL, or dataset ID. `Strict GESIS Hits` means any qrels-relevant GESIS dataset was found through DOI, landing-page URL, or dataset ID.

Precision@k is available but should not be the main title-search metric because a known-item query normally has one target while the denominator remains `k`.

## Reports

The curated current comparison is under `reports/model_comparison/`:

- `INTERPRETATION.md`: concise provider and variant-comparison interpretation.
- `provider_variant_comparison_summary.csv`: compact OpenAI/OpenWebUI/Gemini query-level table for V1/V2/V3/V6 where available.
- `provider_strict_source_gesis_summary.csv`: compact strict source/GESIS hit table for V1/V6 provider context.
- `openai_gemini_variant_comparison_summary.csv`: compact OpenAI/Gemini comparison for V1/V2/V3/V6.
- `openai_variant_comparison_summary.csv`: earlier OpenAI-only comparison for V1/V2/V6, including source-dataset-level aggregation.
- `v1_queries.csv`, `v2_queries.csv`, `v3_queries.csv`, and `v6_queries.csv`: prompts used in the current experiment.
- `v1_provider_difference_summary.csv` and `v6_provider_difference_summary.csv`: OpenAI/OpenWebUI query-level comparison summaries.
- `v1_provider_differences.csv` and `v6_provider_differences.csv`: per-query provider comparison.
- `v1_provider_outputs_query_level.csv` and `v6_provider_outputs_query_level.csv`: selected query-level outputs from both providers.
- `v1_gemini_outputs_labeled.csv`, `v2_gemini_outputs_labeled.csv`, and `v6_gemini_outputs_labeled.csv`: Gemini returned items with source/GESIS relevance labels.
- `v3_openai_outputs_labeled.csv` and `v3_gemini_outputs_labeled.csv`: V3 title-baseline returned items with source/GESIS relevance labels.

Prompt-only exports are under `reports/generated_prompts/`. They cover the random-100 and top-10 OpenAI/Gemini web-search experiments. V1/V2/V3 are shared because their prompts are identical across providers; V6 has provider-specific files because the existing abstract-derived query text differs. Regenerate them with:

```bash
python -m src.export_generated_prompts
```

Start with `reports/model_comparison/INTERPRETATION.md`, then use the CSV files to inspect individual models, queries, and returned datasets.

After rerunning evaluation and audit for the random-100 OpenAI and Gemini experiments, refresh the main comparison files with:

```bash
python -m src.build_main_report
```

## OpenWebUI Notes

For `WEB_SEARCH`, the current OpenWebUI configuration uses the native chat-completions endpoint and `openwebui_web_search_mode: tool_ids`. Web search must also be enabled for the selected model on the OpenWebUI server.

A successful HTTP response is not sufficient: a model can return a tool call without a final answer. These cases are visible in the raw logs and are counted separately by `audit_results`. By default the pipeline sends `tool_choice: "none"` (`openwebui_tool_choice`) so models answer directly instead of calling OpenWebUI's workspace tools; see [Why `tool_choice: "none"`](#why-tool_choice-none) below.

### Why `tool_choice: "none"`

The GESIS OpenWebUI server binds workspace tools (`search_knowledge_files`, `query_knowledge_files`, `search_knowledge_bases`, `search_notes`, `search_chats`) to some model configurations. These search the user's uploaded documents, notes, and chat history — not the GESIS dataset catalog. Reasoning models such as `gpt-5` and `gpt-5.4` call these tools instead of answering, returning `content: null` with `finish_reason: tool_calls`, so they never produce a usable result. Sending `tool_choice: "none"` forbids these calls and forces a direct answer; it does not disable server-side web search, which OpenWebUI injects into the prompt rather than exposing as a model-called tool. Suppressing the workspace tools also keeps the comparison fair: every model answers from its own knowledge (plus web search when enabled) under identical conditions, rather than being influenced by whatever happens to be in a given workspace.
