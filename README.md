# Dataset Findability Experiments

Test whether LLMs discover research datasets from titles or descriptive metadata.
The pipeline generates prompts, calls a provider, matches returned datasets against
the metadata catalogue, and audits the evaluation.

## Start Here

- [Current results and interpretation](reports/README.md)
- [Shared experiment configuration](experiment.yaml)
- [Optional standalone OpenWebUI configuration](config_openwebui.yaml)
- Published-result inputs: `output/current_results_sources/` (local, not tracked).
- Historical experiments and retired files: `output/archive/` (local, not tracked).

Do not edit generated report tables manually. Rebuild them from the saved inputs.

## Installation

Use the same Python environment for installation and execution:

```powershell
conda activate gesis-findability
python -m pip install -r requirements.txt
```

Set the relevant key in the terminal. Never commit keys:

```powershell
$env:OPENAI_API_KEY = "YOUR_KEY"
$env:GEMINI_API_KEY = "YOUR_KEY"
$env:OPENWEBUI_API_KEY = "YOUR_KEY"
```

On Linux, use `export OPENAI_API_KEY='YOUR_KEY'` and the corresponding names for
the other providers. Only keys for providers you use are needed.

## Experiment Choices

Use `experiment.yaml` instead of a configuration for every combination.

| Parameter | Choices |
| --- | --- |
| `--provider` | `openai`, `gemini`, `openwebui` |
| `--sample` | `random100`, `top10` |
| `-V` | `V1`: all topics + country + decade; `V2`: one topic + country + decade; `V3`: title; `V6`: V1 + abstract-derived research need |
| `--template` | `default`, `title_original`, `title_download`, `metadata_search`, `metadata_download`, `abstract_research_need`, `abstract_download` |
| `--limit` | Number of source rows; omit for the configured sample size |
| `--model` | Optional provider model override |

Population templates for V4/V5 are also retained in `experiment.yaml`.
`--limit 5` selects the first five rows of the saved sample, not a new random sample.
Metadata variants can generate fewer queries because required fields are missing;
V2 can generate several queries per dataset.

Preview settings without files or API calls:

```powershell
python -m src.run_pipeline --provider gemini --sample random100 -V V3 --limit 5 --dry-run
```

Run all four stages for one experiment:

```powershell
python -m src.run_pipeline --provider gemini --sample random100 -V V3
python -m src.run_pipeline --provider openai --sample top10 -V V3 --template title_download
```

Each invocation creates a unique directory under `output/experiments/`, with the
resolved configuration, input hashes, stage status, prompts, raw responses and
evaluation files. Existing published inputs are not overwritten.

To run several variants in PowerShell:

```powershell
foreach ($v in @("V1", "V2", "V3", "V6")) {
    python -m src.run_pipeline --provider gemini --sample random100 -V $v
    if ($LASTEXITCODE -ne 0) { break }
}
```

Resume selected stages using the directory printed by the runner:

```powershell
python -m src.run_pipeline --run-dir "output/experiments/RUN_NAME" --stages match_and_eval audit_results
```

Retrieval calls can incur API charges. V6 query generation also calls the configured
abstract generator for uncached datasets. Share the generated V6 wording across
providers for a controlled comparison; do not regenerate it independently.

### Search Settings

The shared OpenAI profile does not currently force search. To require it for new
experiments, add `openai_web_search_tool_choice: required` under
`providers.openai` in `experiment.yaml`. The published OpenAI runs used required
search; their exact settings remain in their saved run configurations.

Gemini receives the Google Search tool, but enabling it does not prove it was used.
The response audits distinguish recorded grounding evidence from absent evidence.
OpenWebUI also depends on the deployment's tool execution configuration.

There is no dataset-count limit in the prompts and no saved-item cap.
`top_k_return: 10` is retained for top-k evaluation, not a request to return ten items.

## Inputs and Outputs

Keep these local metadata files:

- `random_100_datasets_full_metadata.csv`: the fixed random sample.
- `top 10/requested_10_datasets_full_metadata.csv`: the popular-dataset sample.
- `all_research_data_full_metadata.csv`: the full matching and relevance catalogue.

| Output | Purpose |
| --- | --- |
| `queries.csv` | Query text, full prompts and source dataset metadata |
| `logs/` | Raw API responses and recorded request information |
| `llm_results.csv` | Parsed items returned by the model |
| `qrels.csv` | Catalogue datasets considered relevant to each query |
| `per_query_results.csv` | Returned items with matching and relevance labels |
| `metrics_per_query.csv` | Request-level evaluation |
| `metrics_summary.csv` | Aggregated metrics |
| `metrics_*audit*.csv` | Evaluation and response-status checks |

CSV outputs use semicolons. A catalogue match is not a live check that a URL resolves
to the correct dataset; the publication includes a separate title-only link audit.
Metric definitions, limitations, and denominators are explained in the current report.

## Existing Runs and Reports

For individual stages, use the saved configuration for that run:

```powershell
python -m src.match_and_eval --config "PATH_TO_SAVED_CONFIG.yaml"
python -m src.audit_results --config "PATH_TO_SAVED_CONFIG.yaml"
```

Rebuild the publication from `output/current_results_sources/`, without API calls:

```powershell
python -m scripts.build_publication_report --include-link-audit
python -m scripts.build_publication_report --check
```

After an intentional matching-code correction, reevaluate all selected saved runs:

```powershell
python -m scripts.reevaluate_publication_results
python -m scripts.build_publication_report --include-link-audit
```

This preserves saved prompts, model responses and existing qrels, backs up previous
evaluations, and refreshes matching, metrics and audits. Rebuild qrels separately
if the catalogue or relevance rules change.

To prepare a new required-search OpenAI repetition from the saved prompts:

```powershell
python -m scripts.run_openai_required
```

Preparation makes no API calls. Follow its printed `--execute` command only when
ready to incur charges. It covers both samples and V1/V2/V3/V6 in separate folders.

The standalone OpenWebUI configuration remains compatible with individual stages:

```powershell
python -m src.generate_queries --config config_openwebui.yaml -V V3
python -m src.run_llm --config config_openwebui.yaml -V V3
python -m src.match_and_eval --config config_openwebui.yaml -V V3
python -m src.audit_results --config config_openwebui.yaml -V V3
```

## Web Interface

```powershell
python -m pip install -r requirements-web.txt
python -m streamlit run app.py
```

Open the local URL printed by Streamlit. The interface uses shared experiment
profiles and saves separate run directories. Do not expose it publicly without
access control and appropriate handling of API credentials.

## Tests

```powershell
python -m unittest discover -s tests
```

Tests use fixtures and mocks, not paid model calls. Retired configurations and
historical scripts are archived locally, not required by this workflow.
