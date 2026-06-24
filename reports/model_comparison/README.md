# Model Comparison Results

This folder contains the curated result tables for comparing LLM-based discovery of GESIS datasets.

Start with `INTERPRETATION.md`, the single consolidated study report, and use the CSV files as supporting evidence.

## Query Variants

- `v1_all_topics`: one query per dataset using all available topics, country, and decade.
- `v2_single_topic`: one query per topic, plus country and decade.
- `v3_title_only`: one query using only the dataset title.
- `v4_population_unit`: V1 plus study population and unit of analysis; 21 source datasets had all required metadata.
- `v5_population`: V1 plus study population only. The variant is implemented, but results are not included yet.

## Files

- `INTERPRETATION.md`: consolidated pilot setup, model comparison, and interpretation.
- `*_summary.csv`: main comparison table. Use these for reporting.
- `*_response_status.csv`: response coverage diagnostics, showing how often models returned items, empty lists, or tool-only responses.
- `*_queries.csv`: generated query text, source metadata, and the complete initial NO_WEB and WEB_SEARCH prompts, including the top-10 and JSON-format instructions.
- `*_model_outputs_top10_labeled.csv`: datasets returned by each model/mode/query up to rank 10, including matched dataset ID and relevance label.

## Main Metrics

- `coverage_rate`: share of requests where the model returned at least one usable item.
- `hit_at_k_all_queries`: share of all queries where the target/relevant dataset was found in the top-k results.
- `mrr_all_queries`: rewards finding the relevant dataset at higher ranks.
- `ndcg_at_k_all_queries`: ranking quality over top-k results.
- `exact_hit_at_k_all_queries`: hit rate based on exact ID/DOI/URL matches.
- `fuzzy_hit_at_k_all_queries`: hit rate based only on fuzzy title matching.

The `*_summary.csv` files use all requests as the denominator, so empty responses and unfinished tool calls count as failures. This is the fairest version for model comparison.

The `*_model_outputs_top10_labeled.csv` files include `is_relevant`, `matched_dataset_id`, `match_confidence`, and `link_valid` so returned datasets can be inspected directly. Full request/response logs are much larger and are kept outside this report folder.

## High-Level Reading

- Title search (`v3_title_only`) performs best by a large margin.
- Metadata-based search (`v1_all_topics` and `v2_single_topic`) is much harder.
- Adding population and unit of analysis in V4 did not improve exact retrieval on the 21-query paired subset.
- Web search improves coverage for several GPT models, especially `gpt-5.1`.
- Coverage-aware metrics are important because some models return empty responses often.
- V4 fuzzy hits require manual review because several conflicting or unresolved returned identifiers were incorrectly credited through title similarity.
