# Current Report: Provider and Variant Comparison

This folder contains the curated results for the current dataset-discovery experiment.

The report is organized in three parts:

1. Provider context: compare OpenAI API, GESIS OpenWebUI, and Gemini where available.
2. Main variant comparison: compare OpenAI and Gemini for V1, V2, and V6.
3. Prompt inspection: provide the query texts and complete prompts used in the current experiment.

Older pilot variants and earlier broad model-comparison files have been removed from this report folder to keep the material focused.

## Prompt Variants

- `V1_TOPIC_COUNTRY_TIME_ALL_TOPICS`: all topics, country, and decade.
- `V2_TOPIC_COUNTRY_TIME_SINGLE_TOPIC`: one topic at a time, plus country and decade.
- `V6_TOPIC_COUNTRY_TIME_ABSTRACT_NATURAL_LANGUAGE`: V1 plus a natural-language research need generated from the dataset abstract.

The prompts contain no returned-item threshold, and the pipeline saves all returned items. The strict metrics use DOI, landing-page URL, or dataset ID matches.

## Main Comparison

| Variant | Provider | Requests | Strict Source Hits | Source Hits | Strict GESIS Hits | GESIS Hits |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| V1 | OpenAI | 85 | 6 / 85 = 0.071 | 9 / 85 = 0.106 | 21 / 85 = 0.247 | 32 / 85 = 0.376 |
| V1 | Gemini | 85 | 1 / 85 = 0.012 | 3 / 85 = 0.035 | 18 / 85 = 0.212 | 23 / 85 = 0.271 |
| V2 | OpenAI | 250 | 14 / 250 = 0.056 | 16 / 250 = 0.064 | 54 / 250 = 0.216 | 58 / 250 = 0.232 |
| V2 | Gemini | 250 | 6 / 250 = 0.024 | 8 / 250 = 0.032 | 32 / 250 = 0.128 | 41 / 250 = 0.164 |
| V6 | OpenAI | 87 | 23 / 87 = 0.264 | 30 / 87 = 0.345 | 37 / 87 = 0.425 | 46 / 87 = 0.529 |
| V6 | Gemini | 87 | 28 / 87 = 0.329 | 32 / 87 = 0.376 | 37 / 87 = 0.425 | 44 / 87 = 0.518 |

V6 is the strongest variant for both OpenAI and Gemini. Gemini is weaker for V1 and V2, but competitive for V6.

## Provider Context

| Variant | Provider | Strict Source Hits | Hit Value | Strict GESIS Hits | Hit Value |
| --- | --- | ---: | ---: | ---: | ---: |
| V1 | OpenAI | 6 / 85 | 0.071 | 21 / 85 | 0.247 |
| V1 | OpenWebUI | 0 / 78 | 0.000 | 10 / 78 | 0.128 |
| V1 | Gemini | 1 / 85 | 0.012 | 18 / 85 | 0.212 |
| V6 | OpenAI | 23 / 87 | 0.264 | 37 / 87 | 0.425 |
| V6 | OpenWebUI | 0 / 85 | 0.000 | 13 / 85 | 0.153 |
| V6 | Gemini | 28 / 87 | 0.329 | 37 / 87 | 0.435 |

This check shows that direct provider APIs should be treated separately from OpenWebUI. OpenWebUI retrieved some relevant GESIS datasets, but it did not strictly retrieve the original source datasets in this run.

## Files

- `INTERPRETATION.md`: concise interpretation of the provider and variant comparison.
- `provider_variant_comparison_summary.csv`: compact OpenAI/OpenWebUI/Gemini query-level table for V1/V2/V6 where available.
- `provider_strict_source_gesis_summary.csv`: compact strict source/GESIS hit table for V1/V6 provider context.
- `openai_gemini_variant_comparison_summary.csv`: compact OpenAI/Gemini V1/V2/V6 comparison.
- `openai_variant_comparison_summary.csv`: earlier OpenAI-only V1/V2/V6 comparison, including source-dataset-level aggregation.
- `v1_queries.csv`, `v2_queries.csv`, `v6_queries.csv`: query texts and complete prompts.
- `v1_provider_difference_summary.csv`, `v6_provider_difference_summary.csv`: OpenAI/OpenWebUI provider comparison summaries.
- `v1_provider_differences.csv`, `v6_provider_differences.csv`: per-query OpenAI/OpenWebUI provider comparison.
- `v1_provider_outputs_query_level.csv`, `v6_provider_outputs_query_level.csv`: selected query-level outputs from OpenAI/OpenWebUI.
- `v1_gemini_outputs_labeled.csv`, `v2_gemini_outputs_labeled.csv`, `v6_gemini_outputs_labeled.csv`: Gemini returned items with source/GESIS relevance labels.

## Metric Meaning

`Strict Source Hits` means the original sampled dataset was found through DOI, landing-page URL, or dataset ID.

`Source Hits` means the original sampled dataset was found through identifier or title-based matching.

`Strict GESIS Hits` means any qrels-relevant GESIS dataset was found through DOI, landing-page URL, or dataset ID.

`GESIS Hits` means any qrels-relevant GESIS dataset was found through identifier or title-based matching.

For V2, source-dataset-level results are important because one source dataset can generate multiple single-topic queries.
