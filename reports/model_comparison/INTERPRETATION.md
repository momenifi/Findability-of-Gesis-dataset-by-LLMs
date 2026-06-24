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
- `V4_TOPIC_COUNTRY_TIME_UNIVERSE_ANALYSIS_UNIT_ALL_TOPICS`: V1 plus study population and unit of analysis.

`V5_TOPIC_COUNTRY_TIME_UNIVERSE_ALL_TOPICS`, which removes analysis unit from V4, is implemented as the next experiment but has no results in this report yet.

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

All configured model/mode combinations are shown below. `gpt-oss:latest` was configured only for `NO_WEB`, so it has no `WEB_SEARCH` row.

### V3 Title Only

This is the strongest variant.

#### NO_WEB

| Model | Coverage | Hit@10 | MRR | nDCG@10 |
| --- | ---: | ---: | ---: | ---: |
| gemma3:27b | 1.000 | 0.820 | 0.820 | 0.820 |
| gpt-4.1 | 1.000 | 0.340 | 0.340 | 0.340 |
| llama4:latest | 0.980 | 0.570 | 0.570 | 0.570 |
| o4-mini | 0.210 | 0.100 | 0.100 | 0.100 |
| gpt-5 | 0.050 | 0.050 | 0.050 | 0.050 |
| gpt-5-mini | 0.000 | 0.000 | 0.000 | 0.000 |
| gpt-5.1 | 0.480 | 0.190 | 0.190 | 0.190 |
| gpt-oss:latest | 0.190 | 0.190 | 0.190 | 0.190 |

#### WEB_SEARCH

| Model | Coverage | Hit@10 | MRR | nDCG@10 |
| --- | ---: | ---: | ---: | ---: |
| gemma3:27b | 1.000 | 0.800 | 0.795 | 0.796 |
| gpt-4.1 | 1.000 | 0.260 | 0.260 | 0.260 |
| llama4:latest | 0.990 | 0.490 | 0.485 | 0.486 |
| o4-mini | 0.670 | 0.330 | 0.323 | 0.325 |
| gpt-5 | 0.120 | 0.110 | 0.110 | 0.110 |
| gpt-5-mini | 0.850 | 0.610 | 0.540 | 0.558 |
| gpt-5.1 | 0.950 | 0.310 | 0.310 | 0.310 |

Interpretation:

Title search confirms that the pipeline and evaluation are working. Some models can identify many GESIS datasets from the title alone. Web search does not automatically improve every model; for example, `gemma3:27b` performs similarly with and without web search.

### V2 Single Topic, Country, Time

This is a more realistic discovery setting.

#### NO_WEB

| Model | Coverage | Hit@10 | MRR | nDCG@10 |
| --- | ---: | ---: | ---: | ---: |
| gemma3:27b | 1.000 | 0.000 | 0.000 | 0.000 |
| gpt-4.1 | 1.000 | 0.008 | 0.002 | 0.004 |
| llama4:latest | 0.944 | 0.016 | 0.008 | 0.010 |
| o4-mini | 0.684 | 0.000 | 0.000 | 0.000 |
| gpt-5 | 0.372 | 0.004 | 0.004 | 0.004 |
| gpt-5-mini | 0.244 | 0.000 | 0.000 | 0.000 |
| gpt-5.1 | 0.468 | 0.012 | 0.002 | 0.005 |
| gpt-oss:latest | 0.408 | 0.004 | 0.001 | 0.001 |

#### WEB_SEARCH

| Model | Coverage | Hit@10 | MRR | nDCG@10 |
| --- | ---: | ---: | ---: | ---: |
| gemma3:27b | 1.000 | 0.004 | 0.002 | 0.003 |
| gpt-4.1 | 1.000 | 0.020 | 0.004 | 0.008 |
| llama4:latest | 0.968 | 0.020 | 0.006 | 0.009 |
| o4-mini | 0.760 | 0.012 | 0.003 | 0.005 |
| gpt-5 | 0.156 | 0.004 | 0.001 | 0.001 |
| gpt-5-mini | 0.824 | 0.004 | 0.001 | 0.002 |
| gpt-5.1 | 0.956 | 0.020 | 0.007 | 0.010 |

Interpretation:

Single-topic metadata search is much harder than title search. Web search improves coverage for several GPT models, especially `gpt-5.1`, but hit rates remain low. This suggests that topic, country, and decade are often not specific enough to identify the source dataset reliably.

### V1 All Topics, Country, Time

This variant performs weakest overall.

#### NO_WEB

| Model | Coverage | Hit@10 | MRR | nDCG@10 |
| --- | ---: | ---: | ---: | ---: |
| gemma3:27b | 1.000 | 0.012 | 0.012 | 0.012 |
| gpt-4.1 | 0.988 | 0.000 | 0.000 | 0.000 |
| llama4:latest | 0.953 | 0.024 | 0.018 | 0.019 |
| o4-mini | 0.741 | 0.000 | 0.000 | 0.000 |
| gpt-5 | 0.447 | 0.000 | 0.000 | 0.000 |
| gpt-5-mini | 0.282 | 0.000 | 0.000 | 0.000 |
| gpt-5.1 | 0.318 | 0.000 | 0.000 | 0.000 |
| gpt-oss:latest | 0.388 | 0.000 | 0.000 | 0.000 |

#### WEB_SEARCH

| Model | Coverage | Hit@10 | MRR | nDCG@10 |
| --- | ---: | ---: | ---: | ---: |
| gemma3:27b | 1.000 | 0.012 | 0.006 | 0.007 |
| gpt-4.1 | 1.000 | 0.000 | 0.000 | 0.000 |
| llama4:latest | 0.988 | 0.047 | 0.030 | 0.034 |
| o4-mini | 0.753 | 0.012 | 0.006 | 0.007 |
| gpt-5 | 0.200 | 0.000 | 0.000 | 0.000 |
| gpt-5-mini | 0.859 | 0.012 | 0.012 | 0.012 |
| gpt-5.1 | 0.906 | 0.024 | 0.004 | 0.008 |

Interpretation:

Using all topics together may make the prompt too broad or noisy. A dataset with many topics can produce a query that describes a wide thematic area rather than a specific user need. This may explain why the model returns plausible but not target/relevant datasets.

### V4 All Topics, Population, and Unit of Analysis

V4 extends V1 with `universe_en` and `analysis_unit_en`. Only 21 of the 100 source datasets had all required fields. These 21 queries were sent to 15 model/mode combinations, producing 315 requests. All expected logs are present.

#### NO_WEB

| Model | Coverage | Hit@10 | MRR | nDCG@10 |
| --- | ---: | ---: | ---: | ---: |
| gemma3:27b | 1.000 | 0.000 | 0.000 | 0.000 |
| gpt-4.1 | 0.952 | 0.000 | 0.000 | 0.000 |
| llama4:latest | 0.952 | 0.000 | 0.000 | 0.000 |
| o4-mini | 0.714 | 0.000 | 0.000 | 0.000 |
| gpt-5 | 0.286 | 0.000 | 0.000 | 0.000 |
| gpt-5-mini | 0.095 | 0.000 | 0.000 | 0.000 |
| gpt-5.1 | 0.619 | 0.048 | 0.048 | 0.048 |
| gpt-oss:latest | 0.571 | 0.000 | 0.000 | 0.000 |

#### WEB_SEARCH

| Model | Coverage | Hit@10 | MRR | nDCG@10 |
| --- | ---: | ---: | ---: | ---: |
| gemma3:27b | 1.000 | 0.000 | 0.000 | 0.000 |
| gpt-4.1 | 1.000 | 0.000 | 0.000 | 0.000 |
| llama4:latest | 0.905 | 0.048 | 0.016 | 0.024 |
| o4-mini | 0.619 | 0.048 | 0.016 | 0.024 |
| gpt-5 | 0.095 | 0.000 | 0.000 | 0.000 |
| gpt-5-mini | 0.667 | 0.000 | 0.000 | 0.000 |
| gpt-5.1 | 1.000 | 0.048 | 0.024 | 0.030 |

Interpretation:

Only one of the four credited request-level hits was exact: `gpt-5.1` in NO_WEB mode retrieved `ZA3680` at rank 1. The other three were fuzzy title matches. Manual inspection showed conflicting or unresolved returned identifiers, including titles and DOIs that did not identify the target records. The reported V4 Hit@10 values therefore overstate reliable retrieval.

The strict metadata filter produced exactly one qrel per V4 query because free-text population descriptions rarely repeat exactly. V4 consequently behaves more like target-dataset retrieval than broad discovery. Its prompts are also substantially longer, averaging approximately 476 characters and reaching 1,012 characters.

On the same 21 source datasets, V1 produced five credited request-level hits and V4 produced four; each variant had only one exact hit. This run provides no evidence that adding both population and analysis unit improved retrieval. V5 will test whether population alone offers a better balance between specificity, prompt length, and metadata coverage.

## Model Comparison

The model ranking depends strongly on the prompt type.

For title-only search, `gemma3:27b` is strongest in this run. `llama4:latest` and `gpt-5-mini` also perform well in some modes. `gpt-5.1` has high web-search coverage but lower Hit@10 than the best models.

For metadata search, no model performs strongly. `llama4:latest`, `gpt-4.1`, and `gpt-5.1` are among the better models depending on the variant and mode, but the absolute hit rates are still low. V4 did not show an improvement over V1 on the paired subset.

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
- Adding both population and unit of analysis did not improve exact retrieval in V4.
- The full metadata collection is now used for qrels and returned-record matching.
- Fuzzy matching must be made more conservative before relying on small differences in Hit@10.
- Further work should improve the relevance definition and prompt design.

Recommended next step: prevent conflicting or unresolved returned identifiers from being credited through fuzzy title matching, rerun evaluation without repeating the LLM calls, and then evaluate V5. Repeated runs would also help determine whether observed model differences are stable or caused by response variability.
