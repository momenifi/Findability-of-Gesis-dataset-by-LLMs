# Interpretation: V1/V6 Provider Comparison

This report summarizes the current experiment only: V1 and V6 with web search, comparing OpenAI API and GESIS OpenWebUI.

## Setup

- Query source: 100 sampled GESIS datasets.
- Evaluation corpus: full GESIS metadata file.
- Providers:
  - OpenAI API, model `chat-latest`
  - GESIS OpenWebUI, model `gpt-5.4`
- Prompt variants:
  - V1: all topics, country, and decade.
  - V6: V1 plus a natural-language research need generated from the dataset abstract.
- Retrieval instruction: no returned-item threshold was included in the prompt, and the pipeline saved all returned items.

For V6, both providers used the same generated query texts. This makes the provider comparison cleaner than earlier runs.

## Main Strict Results

| Variant | Provider | Strict Source Hits | Hit Value | Strict GESIS Hits | Hit Value |
| --- | --- | ---: | ---: | ---: | ---: |
| V1 | OpenAI | 6 / 85 | 0.071 | 21 / 85 | 0.247 |
| V1 | OpenWebUI | 0 / 78 | 0.000 | 10 / 78 | 0.128 |
| V6 | OpenAI | 23 / 87 | 0.264 | 37 / 87 | 0.425 |
| V6 | OpenWebUI | 0 / 85 | 0.000 | 13 / 85 | 0.153 |

## Metric Meaning

`Strict Source Hits` answers whether the original sampled dataset was found through a DOI, landing-page URL, or dataset ID.

`Strict GESIS Hits` answers whether any qrels-relevant GESIS dataset was found through a DOI, landing-page URL, or dataset ID.

The strict metrics intentionally exclude fuzzy title-only matches. This is important because title-only matches can be plausible but less reliable for evaluating whether a model found an actual dataset record.

## Interpretation

OpenAI performs better than OpenWebUI in this comparison.

The strongest result is OpenAI V6: it strictly finds the original source dataset in 23 of 87 evaluated queries and finds at least one strict qrels-relevant GESIS dataset in 37 of 87 queries.

V6 improves OpenAI clearly compared with V1. Adding the natural-language research need from the abstract seems to help the OpenAI API search for more specific dataset records.

OpenWebUI retrieves some strict GESIS-relevant datasets, but it does not strictly find the original source datasets in this run. This suggests that the difference is not only the visible prompt text. The web-search/tool pipeline, hidden system instructions, API behavior, or model routing may differ between OpenAI API and GESIS OpenWebUI.

## Summary Statement

In the current V1/V6 provider comparison, OpenAI API outperforms GESIS OpenWebUI under strict identifier-based evaluation. The V6 prompt, which adds a natural-language research need generated from the abstract, improves OpenAI from 6 to 23 strict source hits and from 21 to 37 strict GESIS hits. OpenWebUI retrieves some strict GESIS-relevant datasets but does not strictly retrieve the original source datasets in this run.

The supporting CSV files in this folder contain the query texts, selected model outputs, and per-query provider differences.
