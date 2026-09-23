# Current Report: Provider and Variant Comparison

This folder contains the curated results for the current dataset-discovery experiment.

The report is organized in three parts:

1. Provider context: compare OpenAI API, GESIS OpenWebUI, and Gemini where available.
2. Main variant comparison: compare OpenAI and Gemini for V1, V2, V3, and V6.
3. Prompt inspection: provide the query texts and complete prompts used in the current experiment.
4. Top-10 visibility check: compare whether the most requested/downloaded datasets are easier to find.

Older pilot variants and earlier broad model-comparison files have been removed from this report folder to keep the material focused.

## Prompt Variants

- `V1_TOPIC_COUNTRY_TIME_ALL_TOPICS`: all topics, country, and decade.
- `V2_TOPIC_COUNTRY_TIME_SINGLE_TOPIC`: one topic at a time, plus country and decade.
- `V3_TITLE_ONLY`: exact title search as the discoverability baseline.
- `V6_TOPIC_COUNTRY_TIME_ABSTRACT_NATURAL_LANGUAGE`: V1 plus a natural-language research need generated from the dataset abstract.

The prompts contain no returned-item threshold, and the pipeline saves all returned items. The strict metrics use DOI, landing-page URL, or dataset ID matches.

## Main Comparison

| Variant | Provider | Requests | Strict Source Hits | Source Hits | Strict GESIS Hits | GESIS Hits |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| V1 | OpenAI | 85 | 7 / 85 = 0.082 | 10 / 85 = 0.118 | 21 / 85 = 0.247 | 33 / 85 = 0.388 |
| V1 | Gemini | 85 | 1 / 85 = 0.012 | 3 / 85 = 0.035 | 18 / 85 = 0.212 | 23 / 85 = 0.271 |
| V2 | OpenAI | 250 | 14 / 250 = 0.056 | 16 / 250 = 0.064 | 53 / 250 = 0.212 | 57 / 250 = 0.228 |
| V2 | Gemini | 250 | 6 / 250 = 0.024 | 8 / 250 = 0.032 | 32 / 250 = 0.128 | 41 / 250 = 0.164 |
| V3 | OpenAI | 100 | 37 / 100 = 0.370 | 72 / 100 = 0.720 | 37 / 100 = 0.370 | 72 / 100 = 0.720 |
| V3 | Gemini | 100 | 64 / 100 = 0.640 | 78 / 100 = 0.780 | 64 / 100 = 0.640 | 78 / 100 = 0.780 |
| V6 | OpenAI | 87 | 23 / 87 = 0.264 | 30 / 87 = 0.345 | 37 / 87 = 0.425 | 46 / 87 = 0.529 |
| V6 | Gemini | 87 | 28 / 87 = 0.322 | 32 / 87 = 0.368 | 37 / 87 = 0.425 | 44 / 87 = 0.506 |

V3 is the title-search baseline and gives the upper bound for direct discoverability. V6 is the strongest metadata/research-need variant for both OpenAI and Gemini.

The V1, V2, and V3 prompts are identical across OpenAI and Gemini. The existing V6 runs use different abstract-derived research-need wording for the two providers. V6 provider differences therefore combine provider behavior with some prompt variation and should be interpreted cautiously.

## Top-10 Popular Dataset Check

This focused run uses `top 10/requested_10_datasets_full_metadata.csv` as the query source and the full metadata file as the evaluation corpus. It tests whether highly used datasets are more visible to LLM-mediated web search. The current report includes both OpenAI API and Gemini.

| Variant | Provider | Requests | Responses with Items | Coverage | Strict Source Hits | Source Hits | Strict GESIS Hits | GESIS Hits |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| V1 | Gemini | 6 | 6 | 1.000 | 2 / 6 = 0.333 | 2 / 6 = 0.333 | 3 / 6 = 0.500 | 3 / 6 = 0.500 |
| V1 | OpenAI | 6 | 4 | 0.667 | 1 / 6 = 0.167 | 2 / 6 = 0.333 | 3 / 6 = 0.500 | 4 / 6 = 0.667 |
| V2 | Gemini | 67 | 67 | 1.000 | 7 / 67 = 0.104 | 7 / 67 = 0.104 | 18 / 67 = 0.269 | 24 / 67 = 0.358 |
| V2 | OpenAI | 67 | 63 | 0.940 | 5 / 67 = 0.075 | 7 / 67 = 0.104 | 20 / 67 = 0.299 | 28 / 67 = 0.418 |
| V3 | Gemini | 10 | 10 | 1.000 | 9 / 10 = 0.900 | 9 / 10 = 0.900 | 9 / 10 = 0.900 | 9 / 10 = 0.900 |
| V3 | OpenAI | 10 | 10 | 1.000 | 4 / 10 = 0.400 | 7 / 10 = 0.700 | 4 / 10 = 0.400 | 7 / 10 = 0.700 |
| V6 | Gemini | 5 | 5 | 1.000 | 4 / 5 = 0.800 | 4 / 5 = 0.800 | 5 / 5 = 1.000 | 5 / 5 = 1.000 |
| V6 | OpenAI | 5 | 5 | 1.000 | 4 / 5 = 0.800 | 4 / 5 = 0.800 | 5 / 5 = 1.000 | 5 / 5 = 1.000 |

V1 and V6 have fewer than 10 requests because they require complete metadata fields. V2 has more requests because it generates one query per individual topic.

`Source Hits` includes title-based matches, so it is useful for diagnosis but less reliable than `Strict Source Hits`. The file `top10_provider_title_identifier_conflicts.csv` lists cases where the returned title matches one dataset but the DOI/URL resolves to another dataset. These rows should be treated as link/title conflicts, not reliable source retrieval.

Link quality is reported separately:

| Variant | Provider | Returned Item Rows | Suspect Link Rows | Suspect Link Rate |
| --- | --- | ---: | ---: | ---: |
| V3 | OpenAI | 10 | 3 | 0.300 |
| V3 | Gemini | 10 | 0 | 0.000 |
| V6 | OpenAI | 26 | 8 | 0.308 |
| V6 | Gemini | 12 | 3 | 0.250 |

## Provider Context

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

This check shows that direct provider APIs should be treated separately from OpenWebUI. OpenWebUI retrieved some relevant GESIS datasets, but it did not strictly retrieve the original source datasets in this run.

## Files

- `INTERPRETATION.md`: concise interpretation of the provider and variant comparison.
- `provider_variant_comparison_summary.csv`: compact OpenAI/OpenWebUI/Gemini query-level table for V1/V2/V3/V6 where available.
- `provider_strict_source_gesis_summary.csv`: compact strict source/GESIS hit table for V1/V6 provider context.
- `openai_gemini_variant_comparison_summary.csv`: compact OpenAI/Gemini V1/V2/V3/V6 comparison.
- `openai_variant_comparison_summary.csv`: earlier OpenAI-only V1/V2/V6 comparison, including source-dataset-level aggregation.
- `v1_queries.csv`, `v2_queries.csv`, `v3_queries.csv`, `v6_queries.csv`: query texts and complete prompts.
- `v1_provider_difference_summary.csv`, `v6_provider_difference_summary.csv`: OpenAI/OpenWebUI provider comparison summaries.
- `v1_provider_differences.csv`, `v6_provider_differences.csv`: per-query OpenAI/OpenWebUI provider comparison.
- `v1_provider_outputs_query_level.csv`, `v6_provider_outputs_query_level.csv`: selected query-level outputs from OpenAI/OpenWebUI.
- `v1_gemini_outputs_labeled.csv`, `v2_gemini_outputs_labeled.csv`, `v6_gemini_outputs_labeled.csv`: Gemini returned items with source/GESIS relevance labels.
- `v3_openai_outputs_labeled.csv`, `v3_gemini_outputs_labeled.csv`: V3 title-baseline returned items with source/GESIS relevance labels.
- `top10_provider_variant_summary.csv`: compact top-10 OpenAI/Gemini visibility metrics for V1, V2, V3, and V6.
- `top10_provider_response_status.csv`: top-10 response coverage by provider and variant.
- `top10_provider_queries.csv`: top-10 query texts and complete web-search prompts for both providers.
- `top10_provider_outputs_labeled.csv`: top-10 returned items with source/GESIS relevance labels.
- `top10_provider_link_audit_summary.csv`: suspect DOI/URL counts for top-10 V3 and V6 by provider.
- `top10_provider_title_identifier_conflicts.csv`: counts of returned-title and DOI/URL mismatches by provider and variant.
- `../generated_prompts/`: prompt-only CSV files for the random-100 and top-10 OpenAI/Gemini web-search runs, separated by provider and variant.

After rerunning the top-10 evaluation and audit stages, rebuild the combined reporting files with:

```bash
python -m src.build_top10_report
```

After rerunning the random-100 evaluation and audit stages, rebuild the main comparison files with:

```bash
python -m src.build_main_report
```

## Metric Meaning

`Strict Source Hits` means the original sampled dataset was found through DOI, landing-page URL, or dataset ID.

`Source Hits` means the original sampled dataset was found through identifier or title-based matching.

`title_identifier_conflict` means the returned title matched one dataset, but the DOI/URL or dataset identifier resolved to a different dataset. These cases are useful for diagnosing hallucinated or mismatched links and should not be interpreted as reliable source retrieval.

`Strict GESIS Hits` means any qrels-relevant GESIS dataset was found through DOI, landing-page URL, or dataset ID.

`GESIS Hits` means any qrels-relevant GESIS dataset was found through identifier or title-based matching.

For V2, source-dataset-level results are important because one source dataset can generate multiple single-topic queries.
