# Supplementary Live Link Validation

Checked on 24 November 2026. This audit covers only the new OpenAI returned-item
rows marked as source matches but not strict source matches, across both samples
and V1/V2/V3/V6. It does not reclassify the main evaluation.

Current counts are generated in `summary.csv`; the checked row and unique-URL
totals are recorded in `provenance.json`. They are not repeated manually here.
Multiple returned items can belong to one request, and a request can already
have a strict hit in another item. These are not additional query-level hits.

The initial audit found 16 identifier-supported rows spanning 12 requests and
14 distinct returned URLs. All resolved to GESIS catalogue URLs containing the
original SDN identifier. This revealed a defect in SDN ID extraction and canonical
DOI conversion. The matcher is now corrected, both providers and both samples
have been reevaluated, and the affected rows are no longer in this title-only
subset. One further row no longer qualifies as a source match because its
identifier points to a different record. The pre-correction audit is preserved
with the internal evaluation backup; the files here reflect the corrected labels.

Recognizing an identifier is not a complete content/version verification. Some
GESIS pages expose only a generic title (`GESIS-Suche`) in their initial HTML.

Matching-title rows support title identity, but do not establish that
different identifiers represent the same dataset version. Source English and
German title fields were both considered.

## Files

- `title_only_items.csv`: original item labels plus HTTP status, final URL,
  checked time, page title/heading, and separate validation classification.
- `summary.csv`: item counts by sample, variant, and classification.
- `provenance.json`: checksums of the report inputs and scope of the check.

Requests follow redirects and inspect a limited HTML response. Dataset records
rendered only through JavaScript may remain inconclusive. Documents were not
parsed to validate their contents. No authentication or bot protection was
bypassed. A blocked request, timeout, or 502 response does not prove invalidity;
a successful HTTP response does not by itself verify a dataset's identity.

The audit does not call LLM APIs. Cached evidence is stored privately in
`output/current_results_sources/_support/title_only_link_validation/cache/`
and can be reused offline:

```powershell
python -m scripts.validate_title_only_links
```

To fetch uncached links, add `--fetch`. To recheck all links at a later date,
use `--fetch --refresh`; the findings may change as websites change.
