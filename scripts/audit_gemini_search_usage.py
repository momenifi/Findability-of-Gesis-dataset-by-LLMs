"""Audit recorded Google Search grounding in saved Gemini responses, offline."""

import argparse
import csv
import json
from pathlib import Path

from scripts.audit_openai_search_usage import ROOT, VARIANTS, write_csv


def grounding_evidence(response):
    metadata = [candidate.get("groundingMetadata") or {}
                for candidate in response.get("candidates", [])]
    queries = [query for item in metadata for query in item.get("webSearchQueries", [])]
    chunks = [chunk for item in metadata for chunk in item.get("groundingChunks", []) if chunk.get("web")]
    return {
        "grounding_metadata_present": int(any(metadata)),
        "search_queries_recorded": len(queries),
        "web_grounding_chunks": len(chunks),
        "grounding_supports": sum(len(item.get("groundingSupports", [])) for item in metadata),
        "search_entry_point_present": int(any(item.get("searchEntryPoint") for item in metadata)),
        "search_queries": json.dumps(queries, ensure_ascii=True),
    }


def audit(source):
    rows = []
    for variant in VARIANTS:
        directory = source / variant
        with (directory / "metrics_audit_per_request.csv").open(encoding="utf-8-sig", newline="") as handle:
            requests = list(csv.DictReader(handle, delimiter=";"))
        for request in requests:
            filename = request["log_path"].replace("\\", "/").rsplit("/", 1)[-1]
            log = directory / "logs" / filename
            row = {"variant": variant, "query_id": request["query_id"], "model": request["model"],
                   "response_status": request["response_status"], "item_count": request["item_count"],
                   "log_read_status": "ok", "log_path": str(log.relative_to(ROOT))}
            try:
                record = json.loads(log.read_text(encoding="utf-8"))
                attempts = record.get("attempts")
                responses = [attempt.get("response") or {} for attempt in attempts] if isinstance(attempts, list) else [record]
                final = responses[-1] if responses else {}
                evidence = grounding_evidence(final)
                if final.get("error") or request["response_status"] == "api_error":
                    status = "api_error"
                elif evidence["search_queries_recorded"]:
                    status = "search_queries_recorded"
                elif evidence["grounding_metadata_present"]:
                    status = "grounding_metadata_only"
                else:
                    status = "no_recorded_search_evidence"
                evidence["grounding_evidence_any_attempt"] = int(any(
                    grounding_evidence(response)["grounding_metadata_present"] for response in responses))
            except (OSError, ValueError, AttributeError, TypeError):
                row["log_read_status"] = "missing_or_invalid"
                evidence = {key: "" for key in grounding_evidence({})}
                evidence["grounding_evidence_any_attempt"] = ""
                status = "missing_or_invalid_log"
            rows.append({**row, "search_evidence_status": status, **evidence})
    summaries = []
    for variant in VARIANTS:
        group = [row for row in rows if row["variant"] == variant]
        summaries.append({
            "variant": variant, "requests": len(group),
            **{status: sum(row["search_evidence_status"] == status for row in group) for status in (
                "search_queries_recorded", "grounding_metadata_only", "no_recorded_search_evidence",
                "api_error", "missing_or_invalid_log")},
            "grounding_evidence_any_attempt": sum(row["grounding_evidence_any_attempt"] == 1 for row in group),
        })
    write_csv(source / "web_search_usage_per_request.csv", rows)
    write_csv(source / "web_search_usage_summary.csv", summaries)
    return summaries


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / "output/random100_openai_gemini_comparison/gemini")
    args = parser.parse_args()
    print(json.dumps(audit(args.source.resolve()), indent=2))
