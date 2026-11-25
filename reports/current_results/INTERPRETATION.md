# Dataset Discovery with OpenAI and Gemini

This study investigates how readily GESIS research datasets can be discovered
through language-model-assisted search. It compares searching for a known dataset
title with describing a research need using dataset metadata. The aim is to assess
both whether the original dataset is found and whether other relevant GESIS
datasets are suggested.

The experiments use OpenAI API and Gemini with two samples: 100 randomly selected
GESIS datasets and 10 frequently requested/downloaded datasets. The smaller sample
provides an exploratory check of whether popular datasets are easier to discover.

## Study Setup

- Query sources: the random-100 and top-10 samples.
- Evaluation corpus: the full GESIS metadata collection supplied for the study.
- Query designs: exact title, topic/country/time, and an abstract-derived research need.
- Response limit: no maximum number of datasets is specified in the prompts; all
  returned items are retained for inspection.
- Evaluation depth: the reported retrieval metrics assess the first 10 items.
- Evaluation unit: one query. Empty responses and API errors remain in the denominator.

Not every record has the metadata required by every variant, so query counts differ.
The query designs and their implications for those counts are explained below.

## Models and API Access

The same retrieval model was used across both samples and all four query designs
within each provider. The requested model identifiers and response labels were:

| Provider | Requested model | Model label in saved responses | API interface | Execution date |
| --- | --- | --- | --- | --- |
| OpenAI | `chat-latest` | `chat-latest` | Direct OpenAI Responses API | 2026-11-23 |
| Google Gemini | `gemini-3.6-flash` | `gemini-3.6-flash` (`modelVersion`) | Gemini API `generateContent` | 2026-09-23 (researcher-reported) |

OpenAI's execution date is derived from API response creation timestamps in UTC,
not local file modification times. Gemini's date was supplied by the researcher;
its saved responses do not contain execution timestamps and the timezone was not
recorded. Dates document when the models were accessed, but do not independently
identify their underlying snapshots.

`chat-latest` is a model alias rather than a dated, pinned snapshot. The saved
responses do not identify a more specific underlying OpenAI version, so this
report does not equate it with a particular GPT version in the ChatGPT interface. At the time of the experiment, `GPT-6.2` was the latest publicly released GPT model generation.
The Gemini logs likewise record the label above, without a more specific dated
snapshot. Model labels and the provider's search infrastructure are both relevant
when interpreting or attempting to reproduce the results.

Although the configuration files contain `temperature: 0` and `top_p: 1`, the
retrieval request code does not explicitly transmit these sampling parameters
to either API. These controls were therefore left to API defaults, not fixed
as equivalent experimental settings. No reasoning-effort setting was explicitly
sent. The search-tool settings are described separately below.

## What Counts as Found?

Two questions are evaluated separately: finding the original source dataset used
to construct a query, and finding any dataset in its reference relevance set (qrels).
The relevance sets are generated from the full corpus using query metadata; they
are operational judgments, not exhaustive human assessments.

| Metric | Meaning |
| --- | --- |
| Original-dataset discovery: identifier-confirmed | The original source dataset is found through catalogue identifier evidence, such as DOI, dataset ID, or a recognized landing-page URL. |
| Original-dataset discovery: identifier or title | The source is found through identifier evidence or accepted title-based matching. |
| Relevant GESIS dataset discovery: identifier-confirmed | At least one dataset in the reference relevance set is found through identifier evidence. |
| Relevant GESIS dataset discovery: identifier or title | At least one reference-relevant dataset is found through identifier or accepted title matching. |

A **dataset discovery rate** is the percentage of queries finding at least one
qualifying dataset within the first 10 results. Tables give successful queries
divided by all planned queries, followed by that percentage; finding multiple
datasets in one response does not count as multiple successful queries.

The main comparison tables emphasize identifier-confirmed discovery. Broader source/title measures are
also shown in the individual [provider/sample results](README.md). A title match
does not establish that its accompanying link points to the correct dataset;
conversely, an unrecognized link is not necessarily invalid.

## Prompt Variants

| Variant | Query metadata |
| --- | --- |
| V1 | All topics, country, collection decade |
| V2 | One topic, country, collection decade |
| V3 | Exact dataset title |
| V6 | V1 plus an abstract-derived natural-language research need |

V2 can produce several queries per source dataset because it searches topics
individually. Its query-level hit rates should therefore not be read as the
percentage of unique datasets found.

## Rationale for the Query Designs

The variants address progressively less explicit ways of describing a dataset:

1. **Known-title baseline (V3).** Asking for the exact title tests whether the
   provider can identify the dataset and return a corresponding DOI or access
   link when its name is known. This provides a baseline for direct, known-item
   discovery before considering broader searches. It is not a guaranteed upper
   bound: failure in a title query does not prove the dataset is undiscoverable
   through other wording.
2. **Metadata-based discovery (V1 and V2).** Researchers may know a subject,
   geographical area, and period of data collection, but not a dataset title.
   V1 combines all source topics with country and collection decade; V2 uses
   one topic at a time with the same geographical and temporal information.
   This explores the difference between a multi-topic description and a more
   focused single-topic request. Both can legitimately retrieve alternatives
   to the dataset from which the query was constructed.
3. **Natural-language research need (V6).** Adding an abstract-derived description
   to V1 expresses the substantive information a researcher is seeking, rather
   than relying only on catalogue topic labels. This tests whether a richer,
   naturally worded request is associated with better dataset discovery.

Together, the designs distinguish knowing a dataset's name from describing the
data needed for a research question. V6 adds information as well as changing
its expression; differences therefore cannot be attributed to natural wording
alone. The queries approximate researcher information needs but were generated
from dataset metadata, not collected from observed user searches.

### Model Used to Construct Abstract Queries

The saved V6 query files record `gpt-5.4` as the model used to generate the
abstract-derived research-need descriptions for both providers and samples.
This is a query-construction role, separate from the retrieval models listed
above. The generated wording was saved before retrieval rather than regenerated
for each retrieval request. Despite the common generator label, the historical
OpenAI and Gemini V6 files contain different wording; a common model name does
not establish that the generated prompts were identical.

## Provider Search Settings

OpenAI requests required web search (`tool_choice=required`), and execution was
confirmed in the response logs. Gemini requests enabled Google Search, but the
model could decide whether to use it. Most Gemini responses did not include
recorded search-grounding evidence, even when they returned correct dataset links.

The comparison therefore reflects the tested provider configurations, not models
under equivalent web-search conditions. V1, V2, and V3 use identical query wording
across providers; V6 research-need wording differs, which further limits direct
provider comparisons for that variant.

## Random-100 Sample

Both discovery measures below require identifier confirmation.

| Variant | Provider | Queries | Original dataset found | Relevant GESIS dataset found | Empty | API Errors |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| V1 | OpenAI | 85 | 7/85 (8.2%) | 28/85 (32.9%) | 0 | 0 |
| V1 | Gemini | 85 | 1/85 (1.2%) | 19/85 (22.4%) | 0 | 0 |
| V2 | OpenAI | 250 | 10/250 (4.0%) | 41/250 (16.4%) | 0 | 0 |
| V2 | Gemini | 250 | 6/250 (2.4%) | 32/250 (12.8%) | 0 | 0 |
| V3 | OpenAI | 100 | 63/100 (63.0%) | 63/100 (63.0%) | 12 | 0 |
| V3 | Gemini | 100 | 71/100 (71.0%) | 71/100 (71.0%) | 3 | 0 |
| V6 | OpenAI | 87 | 37/87 (42.5%) | 54/87 (62.1%) | 0 | 0 |
| V6 | Gemini | 87 | 29/87 (33.3%) | 38/87 (43.7%) | 1 | 1 |

## Top-10 Sample

Both discovery measures below require identifier confirmation.

| Variant | Provider | Queries | Original dataset found | Relevant GESIS dataset found | Empty | API Errors |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| V1 | OpenAI | 6 | 3/6 (50.0%) | 4/6 (66.7%) | 0 | 0 |
| V1 | Gemini | 6 | 2/6 (33.3%) | 3/6 (50.0%) | 0 | 0 |
| V2 | OpenAI | 67 | 5/67 (7.5%) | 14/67 (20.9%) | 0 | 0 |
| V2 | Gemini | 67 | 7/67 (10.4%) | 18/67 (26.9%) | 0 | 0 |
| V3 | OpenAI | 10 | 10/10 (100.0%) | 10/10 (100.0%) | 0 | 0 |
| V3 | Gemini | 10 | 9/10 (90.0%) | 9/10 (90.0%) | 0 | 0 |
| V6 | OpenAI | 5 | 3/5 (60.0%) | 4/5 (80.0%) | 0 | 0 |
| V6 | Gemini | 5 | 4/5 (80.0%) | 5/5 (100.0%) | 0 | 0 |

## Interpretation

For the random-100 sample, OpenAI identified the source dataset for 63 of 100 title queries (63.0%).
For the random-100 sample, Gemini identified the source dataset for 71 of 100 title queries (71.0%).
For the top-10 sample, OpenAI identified the source dataset for 10 of 10 title queries (100.0%).
For the top-10 sample, Gemini identified the source dataset for 9 of 10 title queries (90.0%).

Rich abstract-derived queries (V6) had higher original-dataset discovery rates than V1/V2 in these samples for both
providers. This suggests that a more detailed research-need description can be
useful, although different query eligibility prevents attributing the differences
solely to the additional abstract information.

The top-10 title results are consistent with greater visibility for popular
datasets, but the small, selected sample cannot establish a popularity effect.
Neither provider is consistently stronger across every sample and variant.

An empty response does not prove that a dataset is undiscoverable, and successful
search execution does not guarantee retrieval of the correct dataset. Returned
titles, identifiers, and links therefore need to be evaluated separately.

A supplementary [live link-validation audit](link_validation/README.md) examines
OpenAI title-only matches separately. It does not alter these discovery counts.

## Evaluation and Limitations

- All planned queries are in the denominator, including empty responses and errors.
- Prompts impose no item limit and all returned items are exported. Discovery rates
  use the existing top-10 evaluation depth; they are not all-rank findability rates.
- Identifier-confirmed original-dataset discovery uses catalogue identifier
  matching, including existing catalogue-equivalence rules. Relevant GESIS
  dataset discovery uses the query's metadata-filter relevance set.
- Measures accepting title matches provide weaker evidence of discovery.
  Title/identifier conflicts are included in returned-item exports for inspection.
- An identifier match or `link_valid` flag is not an independent live-link check.
- Google Search availability is not verified execution: the historical random-100
  Gemini logs record final-response grounding only for V6 query 80. A separate
  three-query diagnostic confirmed correctly submitted search tools but no grounding.
- V6 research-need wording differs across providers; this is not a fully
  controlled V6 provider comparison.
- The top-10 sample is small and selected by popularity. These results do not
  establish that popularity causes visibility. Query eligibility differs by variant.
- Results describe these runs, not a provider-independent discoverability score.
  Model aliases, search indexes, dates and repeated-run variation limit reproducibility.
