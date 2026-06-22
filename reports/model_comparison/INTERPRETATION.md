# Pilot and Model Comparison Report

This report consolidates the pilot setup, current model comparison, and interpretation of LLM-based discovery of GESIS datasets. The CSV files in this folder provide the supporting queries, response diagnostics, metrics, and labeled model outputs.

## Study Design

The study separates the source of test queries from the corpus used to define and match relevant datasets:

- Query source: 100 randomly sampled GESIS datasets from `random_100_datasets_full_metadata.csv`.
- Evaluation corpus: the full metadata collection in `all_research_data_full_metadata.csv`.
- Qrels strategy: metadata filtering using the topic, country, and collection-time values represented in each query.
- Retrieval depth: up to 10 returned datasets per model response.

The first pilot used only the 100-row sample for both query generation and evaluation. That established that title-based known-item retrieval worked, but it also caused plausible datasets outside the sample to be counted as unmatched. The current comparison improves this by evaluating returned datasets and constructing metadata-based qrels against the full corpus.

## What Was Tested

We compared three prompt variants:

- `V3_TITLE_ONLY`: the model receives the dataset title.
- `V2_TOPIC_COUNTRY_TIME_SINGLE_TOPIC`: the model receives one topic, country, and decade.
- `V1_TOPIC_COUNTRY_TIME_ALL_TOPICS`: the model receives all topics together, plus country and decade.

For each variant, we compared different models and two modes:

- `NO_WEB`: the model answers without web search.
- `WEB_SEARCH`: the model can use OpenWebUI web search.

The main evaluation file for each variant is `*_summary.csv`. The most important metrics are `coverage_rate`, `hit_at_k_all_queries`, `mrr_all_queries`, and `ndcg_at_k_all_queries`.

## Evaluation Workflow

`match_and_eval.py` builds qrels, matches returned records to the metadata corpus, labels relevance, and calculates per-query metrics. `audit_results.py` then reconstructs every expected query/model/mode request from the configuration and logs. Missing, empty, error, and unfinished tool-call responses receive zero scores in the audit summaries.

The audit summaries are used in this report because they include all requests in the denominator and therefore avoid overstating models that returned usable results for only a small share of queries.

## Main Finding

The title-only prompt works much better than metadata-based prompts. This is expected and useful: it shows that the pipeline can detect known datasets when the query is specific. The more realistic discovery setting, where users search by topic, country, and time, is much harder.

For reporting, `hit_at_k_all_queries` is the clearest metric. It answers: in how many cases did the model retrieve a relevant or target dataset somewhere in the top 10? `mrr_all_queries` is also useful because it rewards models that place the relevant dataset higher in the ranking.

`precision_at_k_all_queries` should not be emphasized in this pilot. The task is mainly about whether the target or a relevant dataset appears in the returned list, not whether every returned item is relevant.

## Results by Prompt Variant

### V3 Title Only

This is the strongest variant. The best results are:

| Mode | Model | Coverage | Hit@10 | MRR |
| --- | --- | ---: | ---: | ---: |
| NO_WEB | gemma3:27b | 1.00 | 0.82 | 0.82 |
| WEB_SEARCH | gemma3:27b | 1.00 | 0.80 | 0.795 |
| WEB_SEARCH | gpt-5-mini | 0.85 | 0.61 | 0.54 |
| NO_WEB | llama4:latest | 0.98 | 0.57 | 0.57 |
| WEB_SEARCH | llama4:latest | 0.99 | 0.49 | 0.485 |
| WEB_SEARCH | gpt-5.1 | 0.95 | 0.31 | 0.31 |

Interpretation:

Title search confirms that the pipeline and evaluation are working. Some models can identify many GESIS datasets from the title alone. Web search does not automatically improve every model; for example, `gemma3:27b` performs similarly with and without web search.

### V2 Single Topic, Country, Time

This is a more realistic discovery setting. The best results are:

| Mode | Model | Coverage | Hit@10 | MRR |
| --- | --- | ---: | ---: | ---: |
| WEB_SEARCH | gpt-4.1 | 1.00 | 0.020 | 0.0045 |
| WEB_SEARCH | llama4:latest | 0.968 | 0.020 | 0.0059 |
| WEB_SEARCH | gpt-5.1 | 0.956 | 0.020 | 0.0067 |
| NO_WEB | llama4:latest | 0.944 | 0.016 | 0.0083 |
| NO_WEB | gpt-5.1 | 0.468 | 0.012 | 0.0024 |

Interpretation:

Single-topic metadata search is much harder than title search. Web search improves coverage for several GPT models, especially `gpt-5.1`, but hit rates remain low. This suggests that topic, country, and decade are often not specific enough to identify the source dataset reliably.

### V1 All Topics, Country, Time

This variant performs weakest overall. The best results are:

| Mode | Model | Coverage | Hit@10 | MRR |
| --- | --- | ---: | ---: | ---: |
| WEB_SEARCH | llama4:latest | 0.988 | 0.047 | 0.0298 |
| WEB_SEARCH | gpt-5.1 | 0.906 | 0.024 | 0.0040 |
| NO_WEB | llama4:latest | 0.953 | 0.024 | 0.0176 |
| NO_WEB | gemma3:27b | 1.00 | 0.012 | 0.0118 |
| WEB_SEARCH | gemma3:27b | 1.00 | 0.012 | 0.0059 |

Interpretation:

Using all topics together may make the prompt too broad or noisy. A dataset with many topics can produce a query that describes a wide thematic area rather than a specific user need. This may explain why the model returns plausible but not target/relevant datasets.

## Model Comparison

The model ranking depends strongly on the prompt type.

For title-only search, `gemma3:27b` is strongest in this run. `llama4:latest` and `gpt-5-mini` also perform well in some modes. `gpt-5.1` has high web-search coverage but lower Hit@10 than the best models.

For metadata search, no model performs strongly. `llama4:latest`, `gpt-4.1`, and `gpt-5.1` are among the better models depending on the variant and mode, but the absolute hit rates are still low.

The comparison should always consider coverage. A model with low coverage may look better or worse depending on whether unanswered cases are included. The audit summaries in this folder use all requests as the denominator, so empty responses and unfinished tool calls count as failures. This is the fairer comparison.

## Web Search vs No Web

Web search is not always better.

For title-only search, some models already know or can infer GESIS records without web search. For metadata search, web search improves coverage for several models, but it does not solve the main retrieval problem. The model still needs to transform broad metadata into the correct dataset record.

This means that web search should be treated as one experimental condition, not as a guaranteed improvement.

## Conclusion

The current evaluation is useful and credible for an initial model comparison:

- The pipeline works.
- The evaluation was audited with all requests included.
- Title-based discovery performs well and can be used as a sanity check.
- Realistic metadata-based discovery is much harder.
- Single-topic prompts are probably more interpretable than all-topic prompts.
- The full metadata collection is now used for qrels and returned-record matching.
- Further work should improve the relevance definition and prompt design.

Recommended next step: manually inspect a stratified sample of labeled results to validate the metadata-filter qrels, then compare additional prompt formulations for time expressions, such as exact year ranges versus decades. Repeated runs would also help determine whether observed model differences are stable or caused by response variability.
