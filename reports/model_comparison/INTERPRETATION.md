# Interpretation: Provider Check and OpenAI Variant Comparison

This report summarizes the current experiment in two steps. First, V1 and V6 are compared across OpenAI API and GESIS OpenWebUI to check whether the provider setup affects dataset discovery. Second, the analysis continues with OpenAI only and compares V1, V2, and V6.

## Setup

- Query source: 100 sampled GESIS datasets.
- Evaluation corpus: full GESIS metadata file.
- Mode: web search.
- Retrieval instruction: no returned-item threshold was included in the prompt, and the pipeline saved all returned items.
- Strict matching: hits are credited through DOI, landing-page URL, or dataset ID. Fuzzy title-only matches are excluded from the strict metrics.

The main distinction in the results is:

- `Strict Source Hits`: the original sampled dataset was found.
- `Strict GESIS Hits`: any qrels-relevant GESIS dataset was found.

## Provider Check: OpenAI vs OpenWebUI

The provider check uses V1 and V6:

- V1: all topics, country, and decade.
- V6: V1 plus a natural-language research need generated from the dataset abstract.

For V6, both providers used the same generated query texts. This makes the provider comparison cleaner than earlier runs.

| Variant | Provider | Strict Source Hits | Hit Value | Strict GESIS Hits | Hit Value |
| --- | --- | ---: | ---: | ---: | ---: |
| V1 | OpenAI | 6 / 85 | 0.071 | 21 / 85 | 0.247 |
| V1 | OpenWebUI | 0 / 78 | 0.000 | 10 / 78 | 0.128 |
| V6 | OpenAI | 23 / 87 | 0.264 | 37 / 87 | 0.425 |
| V6 | OpenWebUI | 0 / 85 | 0.000 | 13 / 85 | 0.153 |

OpenAI performs better than OpenWebUI under strict identifier-based evaluation. OpenWebUI retrieves some strict GESIS-relevant datasets, but it does not strictly retrieve the original source datasets in this run.

This provider difference is a reason to continue the main prompt-variant analysis with OpenAI API. The difference likely reflects more than the visible prompt text: web-search implementation, tool handling, hidden system instructions, API behavior, or model routing may differ between OpenAI API and GESIS OpenWebUI.

## OpenAI-Only Variant Comparison

After the provider check, the current variant comparison uses OpenAI API only.

- V1: all topics, country, and decade.
- V2: one topic at a time, plus country and decade.
- V6: all topics, country, decade, and natural-language research need from the abstract.

### Query-Level View

This treats every generated query separately. V2 has more queries because one source dataset can generate several single-topic prompts.

| Variant | Queries | Strict Source Hits | Source Hits | Strict GESIS Hits | GESIS Hits |
| --- | ---: | ---: | ---: | ---: | ---: |
| V1 | 85 | 6 / 85 = 0.071 | 9 / 85 = 0.106 | 21 / 85 = 0.247 | 32 / 85 = 0.376 |
| V2 | 250 | 14 / 250 = 0.056 | 16 / 250 = 0.064 | 54 / 250 = 0.216 | 58 / 250 = 0.232 |
| V6 | 87 | 23 / 87 = 0.264 | 30 / 87 = 0.345 | 37 / 87 = 0.425 | 46 / 87 = 0.529 |

On a query-level denominator, V2 is not better than V1. It produces more total hits, but it also produces many more queries.

### Source-Dataset-Level View

This asks whether at least one query for a source dataset succeeded. This view is useful for V2 because it has multiple queries per source dataset.

| Variant | Source Datasets | Strict Source Dataset Hits | Source Dataset Hits | Strict GESIS Dataset Hits | GESIS Dataset Hits |
| --- | ---: | ---: | ---: | ---: | ---: |
| V1 | 85 | 6 / 85 = 0.071 | 9 / 85 = 0.106 | 21 / 85 = 0.247 | 32 / 85 = 0.376 |
| V2 | 84 | 11 / 84 = 0.131 | 13 / 84 = 0.155 | 35 / 84 = 0.417 | 37 / 84 = 0.440 |
| V6 | 87 | 23 / 87 = 0.264 | 30 / 87 = 0.345 | 37 / 87 = 0.425 | 46 / 87 = 0.529 |

In this source-dataset-level view, V2 improves over V1. Splitting topics into separate prompts can help retrieve at least one relevant GESIS dataset for more source datasets. However, V6 remains strongest overall, especially for finding the original source dataset.

## Summary

The provider check shows that OpenAI API gives stronger strict retrieval results than GESIS OpenWebUI in the current setup. Therefore, the main prompt-variant comparison continues with OpenAI only.

Within OpenAI, V6 is currently the best-performing variant. Adding a natural-language research need generated from the abstract improves strict source retrieval and strict GESIS retrieval compared with V1. V2 is useful when evaluated at the source-dataset level, but it does not outperform V6.

The supporting CSV files in this folder contain the query texts, provider comparison files, and OpenAI variant summary.
