# Interpretation: Provider and Variant Comparison

This report summarizes the current dataset-discovery experiment. The main comparison now focuses on web-search runs for V1, V2, and V6, with OpenAI API and Gemini. GESIS OpenWebUI is kept as provider context because earlier tests showed that OpenWebUI can behave differently from the direct OpenAI API, even with similar visible prompts.

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
- V6: V1 plus a natural-language research need generated from the dataset abstract.

V2 creates more prompts than V1/V6 because one source dataset can produce several single-topic queries. Therefore V2 should be read both at the query level and, where needed, at the source-dataset level.

## Provider Context

The earlier provider check compared OpenAI API and GESIS OpenWebUI for V1 and V6. OpenAI performed better than OpenWebUI under strict identifier-based evaluation.

| Variant | Provider | Strict Source Hits | Hit Value | Strict GESIS Hits | Hit Value |
| --- | --- | ---: | ---: | ---: | ---: |
| V1 | OpenAI | 6 / 85 | 0.071 | 21 / 85 | 0.247 |
| V1 | OpenWebUI | 0 / 78 | 0.000 | 10 / 78 | 0.128 |
| V1 | Gemini | 1 / 85 | 0.012 | 18 / 85 | 0.212 |
| V6 | OpenAI | 23 / 87 | 0.264 | 37 / 87 | 0.425 |
| V6 | OpenWebUI | 0 / 85 | 0.000 | 13 / 85 | 0.153 |
| V6 | Gemini | 28 / 87 | 0.329 | 37 / 87 | 0.435 |

OpenWebUI retrieves some relevant GESIS datasets but is clearly weaker for strict source retrieval in this run. This supports treating direct provider APIs separately from OpenWebUI.

Gemini changes the picture for V6: it is weaker than OpenAI for V1, but competitive or better for V6 on strict source retrieval.

## OpenAI vs Gemini

### Query-Level View

This table treats every generated query as one evaluation unit.

| Variant | Provider | Queries | Strict Source Hits | Source Hits | Strict GESIS Hits | GESIS Hits |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| V1 | OpenAI | 85 | 6 / 85 = 0.071 | 9 / 85 = 0.106 | 21 / 85 = 0.247 | 32 / 85 = 0.376 |
| V1 | Gemini | 85 | 1 / 85 = 0.012 | 3 / 85 = 0.035 | 18 / 85 = 0.212 | 23 / 85 = 0.271 |
| V2 | OpenAI | 250 | 14 / 250 = 0.056 | 16 / 250 = 0.064 | 54 / 250 = 0.216 | 58 / 250 = 0.232 |
| V2 | Gemini | 250 | 6 / 250 = 0.024 | 8 / 250 = 0.032 | 32 / 250 = 0.128 | 41 / 250 = 0.164 |
| V6 | OpenAI | 87 | 23 / 87 = 0.264 | 30 / 87 = 0.345 | 37 / 87 = 0.425 | 46 / 87 = 0.529 |
| V6 | Gemini | 87 | 28 / 87 = 0.329 | 32 / 87 = 0.376 | 37 / 87 = 0.425 | 44 / 87 = 0.518 |

V6 is the strongest variant for both providers. For OpenAI, V6 improves substantially over V1 and V2. For Gemini, V6 also improves strongly and even exceeds OpenAI on strict source hits, while OpenAI is slightly higher on broad GESIS hits.

### Source-Dataset-Level View

For V2, source-dataset-level results are useful because several single-topic queries can belong to the same source dataset. In the current OpenAI run, V2 improves over V1 when evaluated by source dataset, but it still does not outperform V6.

| Variant | Provider | Source Datasets | Strict Source Dataset Hits | Source Dataset Hits | Strict GESIS Dataset Hits | GESIS Dataset Hits |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| V1 | OpenAI | 85 | 6 / 85 = 0.071 | 9 / 85 = 0.106 | 21 / 85 = 0.247 | 32 / 85 = 0.376 |
| V2 | OpenAI | 84 | 11 / 84 = 0.131 | 13 / 84 = 0.155 | 35 / 84 = 0.417 | 37 / 84 = 0.440 |
| V6 | OpenAI | 87 | 23 / 87 = 0.264 | 30 / 87 = 0.345 | 37 / 87 = 0.425 | 46 / 87 = 0.529 |

## Response Quality

After rerunning failed Gemini requests:

- Gemini V1: 85 / 85 requests returned items.
- Gemini V2: 250 / 250 requests returned items.
- Gemini V6: 85 / 87 requests returned items; one request had a Gemini API error and one returned an empty item list.

The remaining Gemini V6 gaps should be reported as provider/API behavior, not as prompt-generation errors.

## Summary

The main result is that V6 is the best prompt design so far. Adding a natural-language research need from the abstract improves retrieval of the original source dataset and relevant GESIS datasets.

OpenAI remains stronger than Gemini for V1 and V2. Gemini is competitive for V6 and has the highest strict source hit count in the current V6 run. OpenWebUI remains useful as an institutional interface, but its results are not equivalent to direct OpenAI API results, so it should not be used as a substitute when the goal is to emulate ChatGPT/OpenAI API behavior.

The supporting CSV files in this folder contain the query texts, provider comparison files, and compact summary tables.
