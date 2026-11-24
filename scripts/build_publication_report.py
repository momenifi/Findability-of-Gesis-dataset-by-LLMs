"""Build the current publication package offline from selected saved results."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import tempfile

import pandas as pd

from scripts.audit_gemini_search_usage import grounding_evidence
from scripts.audit_openai_search_usage import search_evidence


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUN = ROOT / "output/current_results_sources/openai"
VARIANTS = {"V1": "v1_all_topics", "V2": "v2_single_topic", "V3": "v3_title_only",
            "V6": "v6_all_topics_abstract_natural_language"}
FLAGS = {"strict_source": "strict_source_hit_at_k_all", "source": "source_hit_at_k_all",
         "strict_gesis": "strict_gesis_relevant_hit_at_k_all", "gesis": "gesis_relevant_hit_at_k_all"}


def source_root(sample, provider, openai_run=DEFAULT_RUN):
    if provider == "OpenAI":
        return openai_run / sample
    if provider != "Gemini" or sample not in {"random100", "top10"}:
        raise ValueError("Unknown publication sample or provider")
    return ROOT / "output/current_results_sources/gemini" / sample


def write_csv(path, frame):
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".pub-", suffix=".csv", delete=False) as handle:
        temporary = Path(handle.name)
    try:
        frame.to_csv(temporary, sep=";", index=False, encoding="utf-8-sig")
        if not path.exists() or temporary.read_bytes() != path.read_bytes():
            temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def build(openai_run, destination):
    manifest = json.loads((openai_run / "manifest.json").read_text(encoding="utf-8"))
    if manifest["search_tool_choice"] != "required":
        raise ValueError("Select a required-search OpenAI run")
    provenance = []
    dates_path = ROOT / "output/current_results_sources/_support/execution_dates.json"
    reported_dates = json.loads(dates_path.read_text(encoding="utf-8")) if dates_path.exists() else {}
    if dates_path.exists():
        provenance.append({"path": str(dates_path.relative_to(ROOT)),
                           "sha256": hashlib.sha256(dates_path.read_bytes()).hexdigest()})
    all_summaries = []
    for sample in ("random100", "top10"):
        for provider in ("OpenAI", "Gemini"):
            collected = {key: [] for key in ("queries", "returned_items", "per_request", "qrels", "summary")}
            source = source_root(sample, provider, openai_run)
            for variant, folder in VARIANTS.items():
                directory = source / folder
                frames = {}
                for name in ("queries", "llm_results", "per_query_results", "metrics_audit_per_request", "qrels", "qrels_debug"):
                    path = directory / f"{name}.csv"
                    frames[name] = pd.read_csv(path, sep=";", keep_default_na=False)
                    provenance.append({"sample": sample, "provider": provider, "variant": variant,
                                       "path": str(path.relative_to(ROOT)),
                                       "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
                queries, audit = frames["queries"], frames["metrics_audit_per_request"]
                if audit.query_id.duplicated().any() or set(audit.query_id) != set(queries.query_id):
                    raise ValueError(f"Incomplete or duplicated request audit: {directory}")
                debug = frames["qrels_debug"]
                if not debug.source_id_in_eval_metadata.astype(str).str.lower().eq("true").all():
                    raise ValueError(f"Missing source datasets in evaluation corpus: {directory}")
                if provider == "OpenAI":
                    entry = next(run for run in manifest["runs"] if run["sample"] == sample and run["variant"] == folder)
                    actual = hashlib.sha256((directory / "queries.csv").read_bytes()).hexdigest()
                    if actual != entry["queries_sha256"]:
                        raise ValueError(f"Modified query file: {directory}")
                evidence = []
                for request in audit.to_dict("records"):
                    filename = request["log_path"].replace("\\", "/").rsplit("/", 1)[-1]
                    log = directory / "logs" / filename
                    provenance.append({"sample": sample, "provider": provider, "variant": variant,
                                       "path": str(log.relative_to(ROOT)),
                                       "sha256": hashlib.sha256(log.read_bytes()).hexdigest()})
                    record = json.loads(log.read_text(encoding="utf-8"))
                    attempts = record.get("attempts")
                    response = (attempts[-1].get("response") or {}) if attempts else record
                    if provider == "OpenAI":
                        found = search_evidence(record)
                        if not found["completed_search_actions"]:
                            raise ValueError(f"Required search not confirmed: {log}")
                        found["search_evidence_status"] = "search_recorded"
                    else:
                        found = grounding_evidence(response)
                        found["search_evidence_status"] = (
                            "api_error" if request["response_status"] == "api_error" else
                            "search_queries_recorded" if found["search_queries_recorded"] else
                            "grounding_metadata_only" if found["grounding_metadata_present"] else
                            "no_recorded_search_evidence")
                    created_at = response.get("created_at")
                    found["response_created_at_utc"] = (
                        datetime.fromtimestamp(created_at, timezone.utc).isoformat()
                        if isinstance(created_at, (int, float)) else "")
                    evidence.append(found)
                requests = audit.drop(columns=["log_path"]).reset_index(drop=True)
                requests = pd.concat([requests, pd.DataFrame(evidence)], axis=1)
                # Preserve every parsed returned item, including any absent from evaluation.
                keys = ["query_id", "query_variant", "mode", "model", "rank"]
                raw = frames["llm_results"].drop(columns=["raw_response_path"], errors="ignore")
                labels = frames["per_query_results"].drop(columns=["raw_response_path"], errors="ignore")
                extra = [column for column in labels if column not in raw.columns]
                labeled = raw.merge(labels[keys + extra], on=keys, how="left", validate="one_to_one", indicator=True)
                labeled["evaluation_available"] = labeled.pop("_merge").eq("both").astype(int)
                count = len(audit)
                summary = {"sample": sample, "provider": provider, "variant": variant,
                           "model": ", ".join(audit.model.unique()), "requests": count,
                           "responses_with_items": int(audit.response_status.eq("items").sum()),
                           "empty_responses": int(audit.response_status.eq("zero_items").sum()),
                           "api_errors": int(audit.response_status.eq("api_error").sum()),
                           "execution_dates_utc": ", ".join(sorted({
                               row["response_created_at_utc"][:10] for row in evidence if row["response_created_at_utc"]})),
                           "reported_execution_date": reported_dates.get(provider, {}).get("date", ""),
                           "search_evidence_requests": sum(row["search_evidence_status"] in (
                               "search_recorded", "search_queries_recorded", "grounding_metadata_only") for row in evidence)}
                for label, column in FLAGS.items():
                    summary[f"{label}_hits"] = int(pd.to_numeric(audit[column]).sum())
                    summary[f"{label}_rate"] = summary[f"{label}_hits"] / count
                all_summaries.append(summary)
                collected["summary"].append(pd.DataFrame([summary]))
                for name, frame in (("queries", queries), ("returned_items", labeled),
                                    ("per_request", requests), ("qrels", frames["qrels"])):
                    frame = frame.copy()
                    if name == "qrels":
                        fields = ["query_id", "source_dataset_id", "relevant_dataset_id", "relevant_title",
                                  "relevant_topic", "relevant_country", "relevant_time_collection_years"]
                        frame = frame[[column for column in fields if column in frame]]
                    frame.insert(0, "provider", provider)
                    frame.insert(1, "variant", variant)
                    collected[name].append(frame)
            output = destination / provider.lower() / sample
            output.mkdir(parents=True, exist_ok=True)
            for name, frames in collected.items():
                write_csv(output / f"{name}.csv", pd.concat(frames, ignore_index=True))
            rows = collected["summary"]
            (output / "README.md").write_text(sample_readme(provider, sample, [frame.iloc[0].to_dict() for frame in rows]), encoding="utf-8")
            provider_index = (f"# {provider} Results\n\n"
                              "- [100 random datasets](random100/README.md)\n"
                              "- [Top-10 datasets](top10/README.md)\n\n"
                              "[Provider comparison and limitations](../INTERPRETATION.md)\n")
            (output.parent / "README.md").write_text(provider_index, encoding="utf-8")
    evaluation_code = {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
                       for path in (ROOT / "src/match_and_eval.py", ROOT / "src/audit_results.py")}
    (destination / "provenance.json").write_text(json.dumps({"openai_run": str(openai_run.relative_to(ROOT)),
        "openai_search_setting": "required", "gemini_responses": "Historical saved responses; evaluation refreshed",
        "evaluation": "Both providers reevaluated with corrected SDN identifier handling; saved responses unchanged",
        "evaluation_code_sha256": evaluation_code,
        "files": provenance}, indent=2), encoding="utf-8")
    templates = ROOT / "scripts/report_templates"
    for name, target in (("current_results_README.md", destination / "README.md"),
                         ("link_validation_README.md", destination / "link_validation/README.md")):
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((templates / name).read_bytes())
    return all_summaries


def sample_readme(provider, sample, rows):
    title = "100 Random Datasets" if sample == "random100" else "Top-10 Datasets"
    lines = [f"# {provider}: {title}", "", "Results for this provider and sample only, across V1/V2/V3/V6.", "",
             "OpenAI search was required." if provider == "OpenAI" else "Gemini Google Search was enabled, not required.", "",
             "## Results", "",
             "| Variant | Queries | Original dataset: identifier-confirmed | Original dataset: identifier or title | Relevant GESIS dataset: identifier-confirmed | Relevant GESIS dataset: identifier or title | Empty | Errors |",
             "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for row in rows:
        n = int(row["requests"])
        cells = [f"{int(row[label + '_hits'])}/{n} ({row[label + '_rate']:.1%})"
                 for label in ("strict_source", "source", "strict_gesis", "gesis")]
        lines.append(f"| {row['variant']} | {n} | " + " | ".join(cells) +
                     f" | {int(row['empty_responses'])} | {int(row['api_errors'])} |")
    lines += ["", "## Inspect the Data", "",
              "1. [summary.csv](summary.csv): four variant-level summaries.",
              "2. [queries.csv](queries.csv): the complete prompts and source metadata.",
              "3. [returned_items.csv](returned_items.csv): every returned dataset/link, justification, and evaluation labels.",
              "4. [per_request.csv](per_request.csv): outcomes per query, including empty responses and search evidence.",
              "5. [qrels.csv](qrels.csv): reference datasets considered relevant for each query.", "",
              "Join files using `variant` and `query_id`; returned items also have `rank`.",
              "A dataset discovery rate is the percentage of queries finding at least one",
              "qualifying dataset within the evaluated first 10 results. Each cell shows the",
              "number of successful queries divided by all planned queries, followed by the rate.",
              "Identifier-confirmed discovery requires catalogue identifier evidence; the broader",
              "measure also accepts title-based matching. This is not an independent live-link check.",
              "Metrics use top-10 evaluation depth, although",
              "the prompts impose no item limit and the item export includes every returned row.", "",
              "[Variants, metric definitions, and comparison limitations](../../INTERPRETATION.md)", "",
              "This page is generated from the same saved results as the CSVs. Do not edit counts manually.", ""]
    return "\n".join(lines)


def interpretation(rows):
    execution_dates = {
        provider: ", ".join(sorted({date for row in rows if row["provider"] == provider
                                  for date in row.get("execution_dates_utc", "").split(", ") if date})) or "Not recorded"
        for provider in ("OpenAI", "Gemini")
    }
    for provider in execution_dates:
        if execution_dates[provider] == "Not recorded":
            reported = sorted({row.get("reported_execution_date", "") for row in rows
                               if row["provider"] == provider and row.get("reported_execution_date")})
            if reported:
                execution_dates[provider] = ", ".join(reported) + " (researcher-reported)"
    text = ["# Dataset Discovery with OpenAI and Gemini", "",
            "This study investigates how readily GESIS research datasets can be discovered",
            "through language-model-assisted search. It compares searching for a known dataset",
            "title with describing a research need using dataset metadata. The aim is to assess",
            "both whether the original dataset is found and whether other relevant GESIS",
            "datasets are suggested.", "",
            "The experiments use OpenAI API and Gemini with two samples: 100 randomly selected",
            "GESIS datasets and 10 frequently requested/downloaded datasets. The smaller sample",
            "provides an exploratory check of whether popular datasets are easier to discover.", "",
            "## Study Setup", "",
            "- Query sources: the random-100 and top-10 samples.",
            "- Evaluation corpus: the full GESIS metadata collection supplied for the study.",
            "- Query designs: exact title, topic/country/time, and an abstract-derived research need.",
            "- Response limit: no maximum number of datasets is specified in the prompts; all",
            "  returned items are retained for inspection.",
            "- Evaluation depth: the reported retrieval metrics assess the first 10 items.",
            "- Evaluation unit: one query. Empty responses and API errors remain in the denominator.", "",
            "Not every record has the metadata required by every variant, so query counts differ.",
            "The query designs and their implications for those counts are explained below.", "",
            "## Models and API Access", "",
            "The same retrieval model was used across both samples and all four query designs",
            "within each provider. The requested model identifiers and response labels were:", "",
            "| Provider | Requested model | Model label in saved responses | API interface | Execution date |",
            "| --- | --- | --- | --- | --- |",
            f"| OpenAI | `chat-latest` | `chat-latest` | Direct OpenAI Responses API | {execution_dates['OpenAI']} |",
            f"| Google Gemini | `gemini-3.6-flash` | `gemini-3.6-flash` (`modelVersion`) | Gemini API `generateContent` | {execution_dates['Gemini']} |", "",
            "OpenAI's execution date is derived from API response creation timestamps in UTC,",
            "not local file modification times. Gemini's date was supplied by the researcher;",
            "its saved responses do not contain execution timestamps and the timezone was not",
            "recorded. Dates document when the models were accessed, but do not independently",
            "identify their underlying snapshots.", "",
            "`chat-latest` is a model alias rather than a dated, pinned snapshot. The saved",
            "responses do not identify a more specific underlying OpenAI version, so this",
            "report does not equate it with a particular GPT version in the ChatGPT interface.",
            "The Gemini logs likewise record the label above, without a more specific dated",
            "snapshot. Model labels and the provider's search infrastructure are both relevant",
            "when interpreting or attempting to reproduce the results.", "",
            "Although the configuration files contain `temperature: 0` and `top_p: 1`, the",
            "retrieval request code does not explicitly transmit these sampling parameters",
            "to either API. These controls were therefore left to API defaults, not fixed",
            "as equivalent experimental settings. No reasoning-effort setting was explicitly",
            "sent. The search-tool settings are described separately below.", "",
            "## What Counts as Found?", "",
            "Two questions are evaluated separately: finding the original source dataset used",
            "to construct a query, and finding any dataset in its reference relevance set (qrels).",
            "The relevance sets are generated from the full corpus using query metadata; they",
            "are operational judgments, not exhaustive human assessments.", "",
            "| Metric | Meaning |", "| --- | --- |",
            "| Original-dataset discovery: identifier-confirmed | The original source dataset is found through catalogue identifier evidence, such as DOI, dataset ID, or a recognized landing-page URL. |",
            "| Original-dataset discovery: identifier or title | The source is found through identifier evidence or accepted title-based matching. |",
            "| Relevant GESIS dataset discovery: identifier-confirmed | At least one dataset in the reference relevance set is found through identifier evidence. |",
            "| Relevant GESIS dataset discovery: identifier or title | At least one reference-relevant dataset is found through identifier or accepted title matching. |", "",
            "A **dataset discovery rate** is the percentage of queries finding at least one",
            "qualifying dataset within the first 10 results. Tables give successful queries",
            "divided by all planned queries, followed by that percentage; finding multiple",
            "datasets in one response does not count as multiple successful queries.", "",
            "The main comparison tables emphasize identifier-confirmed discovery. Broader source/title measures are",
            "also shown in the individual [provider/sample results](README.md). A title match",
            "does not establish that its accompanying link points to the correct dataset;",
            "conversely, an unrecognized link is not necessarily invalid.", "",
            "## Prompt Variants", "", "| Variant | Query metadata |", "| --- | --- |",
            "| V1 | All topics, country, collection decade |",
            "| V2 | One topic, country, collection decade |", "| V3 | Exact dataset title |",
            "| V6 | V1 plus an abstract-derived natural-language research need |", "",
            "V2 can produce several queries per source dataset because it searches topics",
            "individually. Its query-level hit rates should therefore not be read as the",
            "percentage of unique datasets found.", "",
            "## Rationale for the Query Designs", "",
            "The variants address progressively less explicit ways of describing a dataset:", "",
            "1. **Known-title baseline (V3).** Asking for the exact title tests whether the",
            "   provider can identify the dataset and return a corresponding DOI or access",
            "   link when its name is known. This provides a baseline for direct, known-item",
            "   discovery before considering broader searches. It is not a guaranteed upper",
            "   bound: failure in a title query does not prove the dataset is undiscoverable",
            "   through other wording.",
            "2. **Metadata-based discovery (V1 and V2).** Researchers may know a subject,",
            "   geographical area, and period of data collection, but not a dataset title.",
            "   V1 combines all source topics with country and collection decade; V2 uses",
            "   one topic at a time with the same geographical and temporal information.",
            "   This explores the difference between a multi-topic description and a more",
            "   focused single-topic request. Both can legitimately retrieve alternatives",
            "   to the dataset from which the query was constructed.",
            "3. **Natural-language research need (V6).** Adding an abstract-derived description",
            "   to V1 expresses the substantive information a researcher is seeking, rather",
            "   than relying only on catalogue topic labels. This tests whether a richer,",
            "   naturally worded request is associated with better dataset discovery.", "",
            "Together, the designs distinguish knowing a dataset's name from describing the",
            "data needed for a research question. V6 adds information as well as changing",
            "its expression; differences therefore cannot be attributed to natural wording",
            "alone. The queries approximate researcher information needs but were generated",
            "from dataset metadata, not collected from observed user searches.", "",
            "### Model Used to Construct Abstract Queries", "",
            "The saved V6 query files record `gpt-5.4` as the model used to generate the",
            "abstract-derived research-need descriptions for both providers and samples.",
            "This is a query-construction role, separate from the retrieval models listed",
            "above. The generated wording was saved before retrieval rather than regenerated",
            "for each retrieval request. Despite the common generator label, the historical",
            "OpenAI and Gemini V6 files contain different wording; a common model name does",
            "not establish that the generated prompts were identical.", "",
            "## Provider Search Settings", "",
            "OpenAI requests required web search (`tool_choice=required`), and execution was",
            "confirmed in the response logs. Gemini requests enabled Google Search, but the",
            "model could decide whether to use it. Most Gemini responses did not include",
            "recorded search-grounding evidence, even when they returned correct dataset links.", "",
            "The comparison therefore reflects the tested provider configurations, not models",
            "under equivalent web-search conditions. V1, V2, and V3 use identical query wording",
            "across providers; V6 research-need wording differs, which further limits direct",
            "provider comparisons for that variant.", ""]
    for sample, title in (("random100", "Random-100 Sample"), ("top10", "Top-10 Sample")):
        text += [f"## {title}", "", "Both discovery measures below require identifier confirmation.", "",
                 "| Variant | Provider | Queries | Original dataset found | Relevant GESIS dataset found | Empty | API Errors |",
                 "| --- | --- | ---: | ---: | ---: | ---: | ---: |"]
        for variant in VARIANTS:
            for row in rows:
                if row["sample"] == sample and row["variant"] == variant:
                    n = row["requests"]
                    text.append(f"| {variant} | {row['provider']} | {n} | {row['strict_source_hits']}/{n} ({row['strict_source_rate']:.1%}) | "
                                f"{row['strict_gesis_hits']}/{n} ({row['strict_gesis_rate']:.1%}) | {row['empty_responses']} | {row['api_errors']} |")
        text.append("")
    title_findings = [f"For {'the random-100 sample' if row['sample'] == 'random100' else 'the top-10 sample'}, "
                      f"{row['provider']} identified the source dataset for "
                      f"{row['strict_source_hits']} of {row['requests']} title queries ({row['strict_source_rate']:.1%})."
                      for row in rows if row["variant"] == "V3"]
    text += ["## Interpretation", "", *title_findings, "",
             "Rich abstract-derived queries (V6) had higher original-dataset discovery rates than V1/V2 in these samples for both",
             "providers. This suggests that a more detailed research-need description can be",
             "useful, although different query eligibility prevents attributing the differences",
             "solely to the additional abstract information.", "",
             "The top-10 title results are consistent with greater visibility for popular",
             "datasets, but the small, selected sample cannot establish a popularity effect.",
             "Neither provider is consistently stronger across every sample and variant.", "",
             "An empty response does not prove that a dataset is undiscoverable, and successful",
             "search execution does not guarantee retrieval of the correct dataset. Returned",
             "titles, identifiers, and links therefore need to be evaluated separately.", "",
             "A supplementary [live link-validation audit](link_validation/README.md) examines",
             "OpenAI title-only matches separately. It does not alter these discovery counts.", "",
             "## Evaluation and Limitations", "",
             "- All planned queries are in the denominator, including empty responses and errors.",
             "- Prompts impose no item limit and all returned items are exported. Discovery rates",
             "  use the existing top-10 evaluation depth; they are not all-rank findability rates.",
             "- Identifier-confirmed original-dataset discovery uses catalogue identifier",
             "  matching, including existing catalogue-equivalence rules. Relevant GESIS",
             "  dataset discovery uses the query's metadata-filter relevance set.",
             "- Measures accepting title matches provide weaker evidence of discovery.",
             "  Title/identifier conflicts are included in returned-item exports for inspection.",
             "- An identifier match or `link_valid` flag is not an independent live-link check.",
             "- Google Search availability is not verified execution: the historical random-100",
             "  Gemini logs record final-response grounding only for V6 query 80. A separate",
             "  three-query diagnostic confirmed correctly submitted search tools but no grounding.",
             "- V6 research-need wording differs across providers; this is not a fully",
             "  controlled V6 provider comparison.",
             "- The top-10 sample is small and selected by popularity. These results do not",
             "  establish that popularity causes visibility. Query eligibility differs by variant.",
             "- Results describe these runs, not a provider-independent discoverability score.",
             "  Model aliases, search indexes, dates and repeated-run variation limit reproducibility.", ""]
    return "\n".join(text)


def check_publication(destination):
    """Rebuild in a temporary directory and compare; never modify the report."""
    provenance = json.loads((destination / "provenance.json").read_text(encoding="utf-8"))
    problems = []
    for item in provenance["files"]:
        path = ROOT / item["path"]
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != item["sha256"]:
            problems.append(f"Changed or missing source: {item['path']}")
    for name, expected in provenance["evaluation_code_sha256"].items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != expected:
            problems.append(f"Evaluation code changed; check whether reevaluation is needed: {name}")
    if problems:
        return problems
    with tempfile.TemporaryDirectory() as temporary:
        rebuilt = Path(temporary)
        rows = build(ROOT / provenance["openai_run"], rebuilt)
        (rebuilt / "INTERPRETATION.md").write_text(interpretation(rows), encoding="utf-8")
        for path in rebuilt.rglob("*"):
            if path.is_file():
                target = destination / path.relative_to(rebuilt)
                if not target.is_file() or target.read_bytes() != path.read_bytes():
                    problems.append(f"Stale or edited export: {path.relative_to(rebuilt)}")
    audit = destination / "link_validation/provenance.json"
    if audit.exists():
        metadata = json.loads(audit.read_text(encoding="utf-8"))
        for name, expected in metadata["input_sha256"].items():
            path = ROOT / name
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                problems.append("Supplementary link audit is stale; rerun scripts.validate_title_only_links")
                break
        for name, expected in metadata.get("output_sha256", {}).items():
            path = audit.parent / name
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                problems.append(f"Edited supplementary audit export: {name}")
    if destination == ROOT / "reports/current_results":
        index = destination.parent / "README.md"
        if not index.is_file() or index.read_bytes() != (ROOT / "scripts/report_templates/reports_README.md").read_bytes():
            problems.append("Stale or edited reports/README.md")
    return problems


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--openai-run", type=Path, default=DEFAULT_RUN)
    parser.add_argument("--destination", type=Path, default=ROOT / "reports/current_results")
    parser.add_argument("--check", action="store_true", help="Check sources and regenerated exports without modifying the report")
    parser.add_argument("--include-link-audit", action="store_true", help="Also rebuild the supplementary audit from cached evidence, without network requests")
    args = parser.parse_args()
    if args.check:
        problems = check_publication(args.destination.resolve())
        for problem in problems:
            print(problem)
        if problems:
            raise SystemExit(1)
        print("Publication is consistent: sources, generated CSVs, interpretation, and link-audit inputs match.")
        raise SystemExit(0)
    rows = build(args.openai_run.resolve(), args.destination.resolve())
    (args.destination / "INTERPRETATION.md").write_text(interpretation(rows), encoding="utf-8")
    if args.destination.resolve() == ROOT / "reports/current_results":
        (args.destination.parent / "README.md").write_bytes((ROOT / "scripts/report_templates/reports_README.md").read_bytes())
    if args.include_link_audit:
        from scripts.validate_title_only_links import audit
        audit(False, report_dir=args.destination.resolve())
    print(f"Built {len(rows)} provider/variant summaries in {args.destination}; no API calls.")
