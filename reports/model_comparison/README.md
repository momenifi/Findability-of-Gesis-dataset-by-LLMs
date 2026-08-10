# V1/V6 Provider Comparison

This folder contains the curated results for the current comparison between OpenAI API and GESIS OpenWebUI. Older pilot variants have been removed from this report folder to keep the material focused.

## What Is Compared

- `V1_TOPIC_COUNTRY_TIME_ALL_TOPICS`: all topics, country, and decade.
- `V6_TOPIC_COUNTRY_TIME_ABSTRACT_NATURAL_LANGUAGE`: V1 plus a natural-language research need generated from the dataset abstract.
- Providers:
  - OpenAI API using `chat-latest`
  - GESIS OpenWebUI using `gpt-5.4`

The V6 comparison uses the same query texts for both providers.

## Main Result

| Variant | Provider | Strict Source Hits | Hit Value | Strict GESIS Hits | Hit Value |
| --- | --- | ---: | ---: | ---: | ---: |
| V1 | OpenAI | 6 / 85 | 0.071 | 21 / 85 | 0.247 |
| V1 | OpenWebUI | 0 / 78 | 0.000 | 10 / 78 | 0.128 |
| V6 | OpenAI | 23 / 87 | 0.264 | 37 / 87 | 0.425 |
| V6 | OpenWebUI | 0 / 85 | 0.000 | 13 / 85 | 0.153 |

`Strict Source Hits` means the original sampled dataset was found through DOI, landing-page URL, or dataset ID.

`Strict GESIS Hits` means any qrels-relevant GESIS dataset was found through DOI, landing-page URL, or dataset ID.

## Files

- `INTERPRETATION.md`: concise interpretation for Janete.
- `provider_strict_source_gesis_summary.csv`: compact table with the main strict source/GESIS metrics.
- `v1_queries.csv`: V1 query texts and complete prompts.
- `v6_queries.csv`: V6 query texts and complete prompts.
- `v1_provider_difference_summary.csv`: query-level OpenAI/OpenWebUI strict GESIS comparison summary for V1.
- `v6_provider_difference_summary.csv`: query-level OpenAI/OpenWebUI strict GESIS comparison summary for V6.
- `v1_provider_differences.csv`: per-query provider comparison for V1.
- `v6_provider_differences.csv`: per-query provider comparison for V6.
- `v1_provider_outputs_query_level.csv`: selected query-level outputs from both providers for V1.
- `v6_provider_outputs_query_level.csv`: selected query-level outputs from both providers for V6.

## How To Read The Result

For the current research question, use the strict metrics rather than broad title-based hits. Strict metrics require a DOI, known landing-page URL, or dataset ID and therefore better reflect whether the model found a real GESIS dataset record.

V6 improves OpenAI substantially compared with V1. OpenWebUI retrieves some strict GESIS-relevant datasets, but it does not strictly find the original source datasets in this run.
