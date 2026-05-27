# Pilot Report: LLM-Mediated Findability on 100 GESIS Datasets

## Setup

This pilot used `random_100_datasets_full_metadata.csv` as the metadata source and evaluated two query variants with OpenWebUI `WEB_SEARCH`.

Outputs are stored in:

- `output/title_websearch/`
- `output/metadata_websearch/`

The evaluation uses `qrels_strategy: metadata_filter`. For title queries, the relevant dataset is the source dataset. For topic/country/time queries, relevant datasets are derived from the metadata by matching query topic, country, and time fields against the metadata sample.

## Variant 1: Title Search

Query variant:

```text
V3_TITLE_ONLY
```

Example query:

```text
Can you find the dataset titled [Federal Parliament Election 1972 (Panel: 2nd Wave, October 1971 - January 1972)]?
```

Summary:

| Metric | Value |
|---|---:|
| Queries | 100 |
| Queries with results | 99 |
| Returned rows | 125 |
| Relevant returned rows | 113 |
| Matched returned rows | 116 |
| Precision@10 | 0.096 |
| Hit@10 | 0.960 |
| Recall@10 | 0.960 |
| MRR | 0.960 |
| nDCG@10 | 0.960 |
| Link valid rate | 0.013 |
| Off-repo rate | 0.035 |

Interpretation:

Title-based search performs strongly. In about 96% of evaluated title queries, the correct/source dataset was found in the top 10, usually at rank 1. Precision@10 is low by design because title search normally has only one expected correct dataset while the denominator is 10.

## Variant 2: Topic/Country/Time Search

Query variant:

```text
V1_TOPIC_COUNTRY_TIME_ALL_TOPICS
```

Time format:

```text
decade
```

Example query:

```text
Can you find datasets related to ["Working conditions", "Occupational health"] in [countries...] during the [2010s]?
```

Summary:

| Metric | Value |
|---|---:|
| Queries | 85 |
| Queries with results | 79 |
| Returned rows | 781 |
| Qrels rows | 135 |
| Relevant returned rows | 18 |
| Matched returned rows | 137 |
| Precision@10 | 0.010 |
| Hit@10 | 0.101 |
| Recall@10 | 0.089 |
| MRR | 0.036 |
| nDCG@10 | 0.044 |
| Link valid rate | 0.009 |
| Off-repo rate | 0.827 |

Interpretation:

Topic/country/time search is much harder than title search. Only about 10% of queries retrieved at least one metadata-defined relevant dataset in the top 10. The high off-repo rate indicates that many returned items could not be matched to the 100-dataset pilot metadata sample. Some returned datasets may still be plausible or real GESIS datasets, but they are counted as non-relevant if they are outside the pilot sample or cannot be matched to a metadata ID.

Queries with relevant hits included examples such as:

- ESENER-2 for working conditions / occupational health in Europe during the 2010s.
- ALLBUS for broad social/political indicators in Germany during the 2010s.
- State Election Study Saarland 2012.
- Consumer Analysis / consumption behavior in Germany during the 1980s.

## Main Takeaways

1. Title-based known-item retrieval works well in the pilot.
2. Topic/country/time discovery is substantially harder and performs weakly against the current 100-dataset qrels.
3. The 100-dataset sample is too small for robust discovery evaluation. Many plausible returned datasets may fall outside the evaluation corpus.
4. A full-corpus qrels strategy is recommended for the next stage: generate test queries from a sample, but define relevant datasets against the full metadata collection.
5. Decade-based time wording is now supported and is more natural for user-like discovery queries.

## Recommended Next Step

Use this pilot to show the contrast between:

- Known-item findability: strong title baseline.
- Metadata-based discovery: promising but currently limited by the small qrels corpus.

For the next evaluation round, use:

```text
query source: sampled metadata rows
qrels source: full metadata corpus
```

This will allow the evaluation to count relevant GESIS datasets beyond the 100-row pilot sample.
