# Gemini: 100 Random Datasets

Results for this provider and sample only, across V1/V2/V3/V6.

Gemini Google Search was enabled, not required.

## Results

| Variant | Queries | Original dataset: identifier-confirmed | Original dataset: identifier or title | Relevant GESIS dataset: identifier-confirmed | Relevant GESIS dataset: identifier or title | Empty | Errors |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| V1 | 85 | 1/85 (1.2%) | 3/85 (3.5%) | 19/85 (22.4%) | 24/85 (28.2%) | 0 | 0 |
| V2 | 250 | 6/250 (2.4%) | 8/250 (3.2%) | 32/250 (12.8%) | 41/250 (16.4%) | 0 | 0 |
| V3 | 100 | 71/100 (71.0%) | 83/100 (83.0%) | 71/100 (71.0%) | 83/100 (83.0%) | 3 | 0 |
| V6 | 87 | 29/87 (33.3%) | 32/87 (36.8%) | 38/87 (43.7%) | 44/87 (50.6%) | 1 | 1 |

## Inspect the Data

1. [summary.csv](summary.csv): four variant-level summaries.
2. [queries.csv](queries.csv): the complete prompts and source metadata.
3. [returned_items.csv](returned_items.csv): every returned dataset/link, justification, and evaluation labels.
4. [per_request.csv](per_request.csv): outcomes per query, including empty responses and search evidence.
5. [qrels.csv](qrels.csv): reference datasets considered relevant for each query.

Join files using `variant` and `query_id`; returned items also have `rank`.
A dataset discovery rate is the percentage of queries finding at least one
qualifying dataset within the evaluated first 10 results. Each cell shows the
number of successful queries divided by all planned queries, followed by the rate.
Identifier-confirmed discovery requires catalogue identifier evidence; the broader
measure also accepts title-based matching. This is not an independent live-link check.
Metrics use top-10 evaluation depth, although
the prompts impose no item limit and the item export includes every returned row.

[Variants, metric definitions, and comparison limitations](../../INTERPRETATION.md)

This page is generated from the same saved results as the CSVs. Do not edit counts manually.
