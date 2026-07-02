# Model Comparison Results

This folder contains the curated result tables for comparing LLM-based discovery of GESIS datasets.

Start with `INTERPRETATION.md`, the single consolidated study report, and use the CSV files as supporting evidence.

## Query Variants

- `v1_all_topics`: one query per dataset using all available topics, country, and decade.
- `v2_single_topic`: one query per topic, plus country and decade.
- `v3_title_only`: one query using only the dataset title.
- `v4_population_unit`: V1 plus study population and unit of analysis; 21 source datasets had all required metadata.
- `v5_population`: V1 plus study population only; 73 unique queries were evaluated.

## Files

- `INTERPRETATION.md`: consolidated pilot setup, model comparison, and interpretation.
- `*_summary.csv`: main comparison table. Use these for reporting.
- `*_response_status.csv`: response coverage diagnostics, showing how often models returned items, empty lists, or tool-only responses.
- `*_queries.csv`: generated query text, source metadata, and the complete initial NO_WEB and WEB_SEARCH prompts, including the top-10 and JSON-format instructions.
- `*_model_outputs_top10_labeled.csv`: datasets returned by each model/mode/query up to rank 10, including matched dataset ID and relevance label.

## Main Metrics

- `coverage_rate`: share of expected model-query requests where the model returned at least one usable dataset item.
- `hit_at_k_all_queries`: share of all expected requests where at least one relevant dataset appears anywhere in the top-k returned items.
- `mrr_all_queries`: mean reciprocal rank; rewards models for placing the first relevant dataset higher in the ranking, with rank 1 receiving 1.0, rank 2 receiving 0.5, and rank 10 receiving 0.1.
- `ndcg_at_k_all_queries`: normalized ranking-quality score for the top-k results; it is most useful when more than one dataset can be relevant because it rewards relevant datasets appearing higher in the list.
- `exact_hit_at_k_all_queries`: share of all expected requests where a relevant dataset was found through an exact identifier, DOI, URL, or equivalent exact match.
- `fuzzy_hit_at_k_all_queries`: share of all expected requests where the hit was credited only through fuzzy title matching, so these cases should be interpreted cautiously and may need manual review.
- `zero_items`: number of requests where the model returned no usable dataset item.
- `tool_calls_only`: number of requests where the model called a tool but did not return a final answer usable by the pipeline.
- `error`: number of requests that failed because of an API, request, or response-parsing error.

The `*_summary.csv` files use all requests as the denominator, so empty responses and unfinished tool calls count as failures. This is the fairest version for model comparison.

The `*_model_outputs_top10_labeled.csv` files include `is_relevant`, `matched_dataset_id`, `match_confidence`, and `link_valid` so returned datasets can be inspected directly. Full request/response logs are much larger and are kept outside this report folder.

## High-Level Reading

- Title search (`v3_title_only`) performs best by a large margin.
- Metadata-based search (`v1_all_topics` and `v2_single_topic`) is much harder.
- Adding population and unit of analysis in V4 did not improve exact retrieval on the 21-query paired subset.
- Population-only V5 also did not improve retrieval over V1 on the corresponding source subset.
- Web search improves coverage for several GPT models, especially `gpt-5.1`.
- Coverage-aware metrics are important because some models return empty responses often.
- V4 fuzzy hits require manual review because several conflicting or unresolved returned identifiers were incorrectly credited through title similarity.
- The same matching issue affects V5; its apparent exact hit was produced by a perfect fuzzy-title score despite conflicting returned ZA identifiers.
