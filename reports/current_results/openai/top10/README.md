# OpenAI: Top-10 Datasets

Results for this provider and sample only, across V1/V2/V3/V6.

OpenAI search was required.

## Results

| Variant | Queries | Original dataset: identifier-confirmed | Original dataset: identifier or title | Relevant GESIS dataset: identifier-confirmed | Relevant GESIS dataset: identifier or title | Empty | Errors |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| V1 | 6 | 3/6 (50.0%) | 3/6 (50.0%) | 4/6 (66.7%) | 5/6 (83.3%) | 0 | 0 |
| V2 | 67 | 5/67 (7.5%) | 7/67 (10.4%) | 14/67 (20.9%) | 27/67 (40.3%) | 0 | 0 |
| V3 | 10 | 10/10 (100.0%) | 10/10 (100.0%) | 10/10 (100.0%) | 10/10 (100.0%) | 0 | 0 |
| V6 | 5 | 3/5 (60.0%) | 4/5 (80.0%) | 4/5 (80.0%) | 5/5 (100.0%) | 0 | 0 |

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
