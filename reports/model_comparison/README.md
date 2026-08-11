# Current Report: Provider Check and OpenAI Variant Comparison

This folder contains the curated results for the current dataset-discovery experiment.

The report is organized in two parts:

1. Provider check: compare OpenAI API and GESIS OpenWebUI for V1 and V6.
2. Main variant comparison: continue with OpenAI API and compare V1, V2, and V6.

Older pilot variants and earlier broad model-comparison files have been removed from this report folder to keep the material focused.

## Prompt Variants

- `V1_TOPIC_COUNTRY_TIME_ALL_TOPICS`: all topics, country, and decade.
- `V2_TOPIC_COUNTRY_TIME_SINGLE_TOPIC`: one topic at a time, plus country and decade.
- `V6_TOPIC_COUNTRY_TIME_ABSTRACT_NATURAL_LANGUAGE`: V1 plus a natural-language research need generated from the dataset abstract.

The prompts contain no returned-item threshold, and the pipeline saves all returned items. The strict metrics use DOI, landing-page URL, or dataset ID matches.

## Provider Check: V1 and V6

| Variant | Provider | Strict Source Hits | Hit Value | Strict GESIS Hits | Hit Value |
| --- | --- | ---: | ---: | ---: | ---: |
| V1 | OpenAI | 6 / 85 | 0.071 | 21 / 85 | 0.247 |
| V1 | OpenWebUI | 0 / 78 | 0.000 | 10 / 78 | 0.128 |
| V6 | OpenAI | 23 / 87 | 0.264 | 37 / 87 | 0.425 |
| V6 | OpenWebUI | 0 / 85 | 0.000 | 13 / 85 | 0.153 |

This check supports using OpenAI API for the main variant comparison. OpenAI gives stronger strict retrieval results in the current setup.

## OpenAI Variant Comparison

### Query-Level

| Variant | Queries | Strict Source Hits | Source Hits | Strict GESIS Hits | GESIS Hits |
| --- | ---: | ---: | ---: | ---: | ---: |
| V1 | 85 | 6 / 85 = 0.071 | 9 / 85 = 0.106 | 21 / 85 = 0.247 | 32 / 85 = 0.376 |
| V2 | 250 | 14 / 250 = 0.056 | 16 / 250 = 0.064 | 54 / 250 = 0.216 | 58 / 250 = 0.232 |
| V6 | 87 | 23 / 87 = 0.264 | 30 / 87 = 0.345 | 37 / 87 = 0.425 | 46 / 87 = 0.529 |

### Source-Dataset-Level

| Variant | Source Datasets | Strict Source Dataset Hits | Source Dataset Hits | Strict GESIS Dataset Hits | GESIS Dataset Hits |
| --- | ---: | ---: | ---: | ---: | ---: |
| V1 | 85 | 6 / 85 = 0.071 | 9 / 85 = 0.106 | 21 / 85 = 0.247 | 32 / 85 = 0.376 |
| V2 | 84 | 11 / 84 = 0.131 | 13 / 84 = 0.155 | 35 / 84 = 0.417 | 37 / 84 = 0.440 |
| V6 | 87 | 23 / 87 = 0.264 | 30 / 87 = 0.345 | 37 / 87 = 0.425 | 46 / 87 = 0.529 |

## Files

- `INTERPRETATION.md`: concise interpretation of the provider check and OpenAI variant comparison.
- `provider_strict_source_gesis_summary.csv`: compact OpenAI vs OpenWebUI strict metric table for V1/V6.
- `openai_variant_comparison_summary.csv`: compact OpenAI-only V1/V2/V6 comparison.
- `v1_queries.csv`, `v2_queries.csv`, `v6_queries.csv`: query texts and complete prompts.
- `v1_provider_difference_summary.csv`, `v6_provider_difference_summary.csv`: provider comparison summaries.
- `v1_provider_differences.csv`, `v6_provider_differences.csv`: per-query provider comparison.
- `v1_provider_outputs_query_level.csv`, `v6_provider_outputs_query_level.csv`: selected query-level outputs from both providers.

## Metric Meaning

`Strict Source Hits` means the original sampled dataset was found through DOI, landing-page URL, or dataset ID.

`Strict GESIS Hits` means any qrels-relevant GESIS dataset was found through DOI, landing-page URL, or dataset ID.

For V2, source-dataset-level results are important because one source dataset can generate multiple single-topic queries.
