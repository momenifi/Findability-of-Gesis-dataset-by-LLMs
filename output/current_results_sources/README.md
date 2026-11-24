# Source Results for the Current Report

These are the actual source folders, moved here rather than copied. This layout
mirrors `reports/current_results/`:

```text
current_results_sources/
  openai/
    random100/
    top10/
  gemini/
    random100/
    top10/
```

Each provider/sample folder contains `v1_all_topics`, `v2_single_topic`,
`v3_title_only`, and `v6_all_topics_abstract_natural_language`.

Each variant contains saved `queries.csv`, `llm_results.csv`, raw API `logs/`,
evaluation/audit CSVs, qrels, and a portable `config.yaml`. Run evaluation/audit
from the repository root. Do not rerun `run_llm` over these completed runs.

OpenAI is the required-search run originally named
`20261123T145051Z_d675e7f7`; its original manifest is retained in `openai/`.
Gemini responses are the historical saved experiments, reevaluated with the
same corrected matching rules. Search settings and limits are documented in
the publication package.

Old absolute file paths inside raw logs are retained as historical records.
The active configs and audit log paths now use the consolidated locations.
The report builder resolves sources through `source_root` in
`scripts/build_publication_report.py`.

Rebuild and check the publication exports, without API calls:

```powershell
python -m scripts.build_publication_report
python -m scripts.build_publication_report --check
```

This source-data folder is excluded from Git by the existing `output/` rule.
Only the curated publication package under `reports/current_results/` is intended
for GitHub. Historical experiments and backups elsewhere in `output/` are not
alternative sources for the current report.

The earlier optional-search random-100 OpenAI run is archived separately at
`output/archive/openai_optional_search_random100/`. It is not a duplicate of the
required-search OpenAI run here.

`_support/title_only_link_validation/cache/` contains cached page evidence needed
to reproduce the supplementary link audit without refetching websites. It is
supporting data, not another dataset sample or provider run.
