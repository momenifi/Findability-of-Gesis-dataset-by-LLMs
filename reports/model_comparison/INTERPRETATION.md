# Interpretation: Provider and Variant Comparison

This report summarizes the current dataset-discovery experiment. The main comparison now focuses on web-search runs for V1, V2, V3, and V6, with OpenAI API and Gemini. GESIS OpenWebUI is kept as provider context because earlier tests showed that OpenWebUI can behave differently from the direct OpenAI API, even with similar visible prompts.

## Setup

- Query source: 100 sampled GESIS datasets.
- Evaluation corpus: full GESIS metadata file.
- Mode: web search only.
- Prompt threshold: no returned-item threshold is included in the prompt.
- Saved model outputs: all returned items are saved.
- Strict matching: hits are credited through DOI, landing-page URL, or dataset ID. Title-only matches are reported separately.

The main metrics used here are:

- `Strict Source Hits`: the original sampled dataset was found through a reliable identifier.
- `Source Hits`: the original sampled dataset was found through identifier or title-based matching.
- `Strict GESIS Hits`: any qrels-relevant GESIS dataset was found through a reliable identifier.
- `GESIS Hits`: any qrels-relevant GESIS dataset was found through identifier or title-based matching.

## Prompt Variants

- V1: all topics, country, and decade.
- V2: one topic at a time, plus country and decade.
- V3: exact title search as the discoverability baseline.
- V6: V1 plus a natural-language research need generated from the dataset abstract.

V3 answers whether the exact source dataset is discoverable when the title is already known. V2 creates more prompts than V1/V3/V6 because one source dataset can produce several single-topic queries. Therefore V2 should be read both at the query level and, where needed, at the source-dataset level.

V1, V2, and V3 use identical prompts for OpenAI and Gemini. V6 does not: the abstract-derived natural-language research need was generated separately and differs between the provider runs. The V6 comparison is therefore indicative rather than a fully controlled provider comparison. A controlled rerun should reuse one fixed V6 query file for both providers.

## Provider Context

The provider check compares OpenAI API and GESIS OpenWebUI for V1 and V6. The OpenWebUI results were reevaluated with the same corrected matching logic used for OpenAI and Gemini. OpenAI performed better than OpenWebUI under strict identifier-based evaluation.

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

OpenWebUI returned usable items for 78 of 85 V1 requests and 85 of 87 V6 requests. It retrieved some strict GESIS-relevant datasets, but it did not retrieve any original source dataset through a reliable identifier. This supports treating direct provider APIs separately from OpenWebUI.

Gemini changes the picture for title search and V6: it is weaker than OpenAI for V1 and V2, but stronger on V3 title-search strict source retrieval and competitive for V6.

## OpenAI vs Gemini

### Query-Level View

This table treats every generated query as one evaluation unit.

| Variant | Provider | Queries | Strict Source Hits | Source Hits | Strict GESIS Hits | GESIS Hits |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| V1 | OpenAI | 85 | 7 / 85 = 0.082 | 10 / 85 = 0.118 | 21 / 85 = 0.247 | 33 / 85 = 0.388 |
| V1 | Gemini | 85 | 1 / 85 = 0.012 | 3 / 85 = 0.035 | 18 / 85 = 0.212 | 23 / 85 = 0.271 |
| V2 | OpenAI | 250 | 14 / 250 = 0.056 | 16 / 250 = 0.064 | 53 / 250 = 0.212 | 57 / 250 = 0.228 |
| V2 | Gemini | 250 | 6 / 250 = 0.024 | 8 / 250 = 0.032 | 32 / 250 = 0.128 | 41 / 250 = 0.164 |
| V3 | OpenAI | 100 | 37 / 100 = 0.370 | 72 / 100 = 0.720 | 37 / 100 = 0.370 | 72 / 100 = 0.720 |
| V3 | Gemini | 100 | 64 / 100 = 0.640 | 78 / 100 = 0.780 | 64 / 100 = 0.640 | 78 / 100 = 0.780 |
| V6 | OpenAI | 87 | 23 / 87 = 0.264 | 30 / 87 = 0.345 | 37 / 87 = 0.425 | 46 / 87 = 0.529 |
| V6 | Gemini | 87 | 28 / 87 = 0.322 | 32 / 87 = 0.368 | 37 / 87 = 0.425 | 44 / 87 = 0.506 |

V3 is the title-search baseline and gives the upper bound for direct discoverability. Gemini is stronger than OpenAI on strict V3 title retrieval. V6 is the strongest metadata/research-need variant for both providers. For OpenAI, V6 improves substantially over V1 and V2. For Gemini, V6 also improves strongly, while OpenAI is slightly higher on broad GESIS hits.

### Source-Dataset-Level View

For V2, source-dataset-level results are useful because several single-topic queries can belong to the same source dataset. In the current OpenAI run, V2 improves over V1 when evaluated by source dataset, but it still does not outperform V6.

| Variant | Provider | Source Datasets | Strict Source Dataset Hits | Source Dataset Hits | Strict GESIS Dataset Hits | GESIS Dataset Hits |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| V1 | OpenAI | 85 | 7 / 85 = 0.082 | 10 / 85 = 0.118 | 21 / 85 = 0.247 | 33 / 85 = 0.388 |
| V2 | OpenAI | 84 | 11 / 84 = 0.131 | 13 / 84 = 0.155 | 36 / 84 = 0.429 | 38 / 84 = 0.452 |
| V6 | OpenAI | 87 | 23 / 87 = 0.264 | 30 / 87 = 0.345 | 37 / 87 = 0.425 | 46 / 87 = 0.529 |

## Response Quality

After rerunning failed Gemini requests:

- Gemini V1: 85 / 85 requests returned items.
- Gemini V2: 250 / 250 requests returned items.
- Gemini V3: 98 / 100 requests returned items; two requests had Gemini API errors.
- Gemini V6: 85 / 87 requests returned items; one request had a Gemini API error and one returned an empty item list.

The remaining Gemini V6 gaps should be reported as provider/API behavior, not as prompt-generation errors.

## Top-10 Popular Dataset Visibility

We also ran a focused web-search test on the top-10 requested/downloaded datasets from `top 10/requested_10_datasets_full_metadata.csv`, using both OpenAI API and Gemini. This checks whether highly used datasets are more visible to LLM-mediated search than the random 100-dataset sample.

| Variant | Provider | Requests | Responses with Items | Coverage | Strict Source Hits | Source/Title Hits | Strict GESIS Hits | GESIS Hits |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| V1 | Gemini | 6 | 6 | 1.000 | 2 / 6 = 0.333 | 2 / 6 = 0.333 | 3 / 6 = 0.500 | 3 / 6 = 0.500 |
| V1 | OpenAI | 6 | 4 | 0.667 | 1 / 6 = 0.167 | 2 / 6 = 0.333 | 3 / 6 = 0.500 | 4 / 6 = 0.667 |
| V2 | Gemini | 67 | 67 | 1.000 | 7 / 67 = 0.104 | 7 / 67 = 0.104 | 18 / 67 = 0.269 | 24 / 67 = 0.358 |
| V2 | OpenAI | 67 | 63 | 0.940 | 5 / 67 = 0.075 | 7 / 67 = 0.104 | 20 / 67 = 0.299 | 28 / 67 = 0.418 |
| V3 | Gemini | 10 | 10 | 1.000 | 9 / 10 = 0.900 | 9 / 10 = 0.900 | 9 / 10 = 0.900 | 9 / 10 = 0.900 |
| V3 | OpenAI | 10 | 10 | 1.000 | 4 / 10 = 0.400 | 7 / 10 = 0.700 | 4 / 10 = 0.400 | 7 / 10 = 0.700 |
| V6 | Gemini | 5 | 5 | 1.000 | 4 / 5 = 0.800 | 4 / 5 = 0.800 | 5 / 5 = 1.000 | 5 / 5 = 1.000 |
| V6 | OpenAI | 5 | 5 | 1.000 | 4 / 5 = 0.800 | 4 / 5 = 0.800 | 5 / 5 = 1.000 | 5 / 5 = 1.000 |

V3 is the clearest popularity baseline. For popular datasets queried by exact title, Gemini found 9 of 10 strict source datasets and OpenAI found 4 of 10. OpenAI still found 7 of 10 by source/title matching, but title-only matches are less reliable because they can hide DOI/title conflicts. V6 performs best among the metadata-style prompts: both providers strictly retrieved the source dataset for 4 of 5 eligible queries and retrieved a strict GESIS-relevant dataset for all 5. Only 5 of the 10 records were eligible because V6 requires topic, country, time, and abstract metadata.

Title-only matches must be interpreted carefully. Some responses contain a returned title that matches the requested dataset but a DOI/URL that resolves to a different dataset. These are counted as `title_identifier_conflict` and should not be treated as reliable source retrieval. In the corrected top-10 V3 evaluation, OpenAI has 3 conflict rows and Gemini has 2. For example, OpenAI V3 query 2 returned the ISSP 2023 title but attached DOI `10.4232/1.14420`, which resolves to `ZA8879` rather than the source dataset `ZA10010`.

The top-10 run supports the hypothesis that popular datasets are more visible, especially when queried by exact title or by a rich abstract-derived research need. Link quality remains a separate issue: in the top-10 title run, suspect DOI/URL rates were 0.300 for OpenAI and 0.000 for Gemini; in V6, they were 0.308 for OpenAI and 0.250 for Gemini.

## Summary

The main result is that V3 provides a necessary discoverability baseline, and V6 is the best realistic prompt design so far when users do not know the exact title. Adding a natural-language research need from the abstract improves retrieval of the original source dataset and relevant GESIS datasets.

OpenAI remains stronger than Gemini for V1 and V2. Gemini is competitive for V6 and has the highest strict source hit count in the current V6 run. OpenWebUI remains useful as an institutional interface, but its results are not equivalent to direct OpenAI API results, so it should not be used as a substitute when the goal is to emulate ChatGPT/OpenAI API behavior.

The supporting CSV files in this folder contain the query texts, provider comparison files, and compact summary tables. Prompt-only files for sharing and inspection are stored under `reports/generated_prompts/`, separated by dataset set, provider, and variant.
