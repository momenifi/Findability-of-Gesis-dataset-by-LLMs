"""Audit actual web-search actions in saved random-100 OpenAI logs, offline."""

import argparse
import csv
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VARIANTS = ("v1_all_topics", "v2_single_topic", "v3_title_only", "v6_all_topics_abstract_natural_language")


def write_csv(path, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), delimiter=";")
        writer.writeheader()
        writer.writerows(rows)


def search_evidence(record):
    attempts = record.get("attempts")
    responses = [a.get("response") or {} for a in attempts] if isinstance(attempts, list) else [record]
    final = responses[-1] if responses else {}
    calls = [item for item in final.get("output", []) if item.get("type") == "web_search_call"]
    actions = Counter((item.get("action") or {}).get("type", "unknown") for item in calls)
    searches = [item for item in calls if (item.get("action") or {}).get("type") == "search"]
    request = (attempts[-1].get("request") or {}) if attempts else {}
    return {
        "response_status_api": final.get("status", ""),
        "tool_choice_recorded": final.get("tool_choice") or request.get("openai_web_search_tool_choice", "not_recorded"),
        "search_used": int(bool(searches)),
        "completed_search_actions": sum(item.get("status") == "completed" for item in searches),
        "search_actions": len(searches),
        "open_page_actions": actions["open_page"],
        "web_tool_calls": len(calls),
        "search_used_any_attempt": int(any(
            item.get("type") == "web_search_call" and (item.get("action") or {}).get("type") == "search"
            for response in responses for item in response.get("output", [])
        )),
    }


def audit(source):
    rows = []
    for variant in VARIANTS:
        directory = source / variant
        with (directory / "metrics_audit_per_request.csv").open(encoding="utf-8-sig", newline="") as handle:
            requests = list(csv.DictReader(handle, delimiter=";"))
        for request in requests:
            # Saved CSV paths can point to the pre-relocation directory.
            filename = request["log_path"].replace("\\", "/").rsplit("/", 1)[-1]
            log = directory / "logs" / filename
            row = {"variant": variant, "query_id": request["query_id"], "model": request["model"],
                   "response_status": request["response_status"], "item_count": request["item_count"],
                   "log_read_status": "ok", "log_path": str(log.relative_to(ROOT))}
            try:
                evidence = search_evidence(json.loads(log.read_text(encoding="utf-8")))
            except (OSError, ValueError, AttributeError, TypeError):
                row["log_read_status"] = "missing_or_invalid"
                evidence = {key: "" for key in search_evidence({})}
            rows.append({**row, **evidence})
    summary = []
    for variant in VARIANTS:
        group = [row for row in rows if row["variant"] == variant]
        known = [row for row in group if row["log_read_status"] == "ok"]
        summary.append({
            "variant": variant, "requests": len(group), "readable_logs": len(known),
            "searched": sum(row["search_used"] == 1 for row in known),
            "not_searched": sum(row["search_used"] == 0 for row in known),
            "items_with_search": sum(row["response_status"] == "items" and row["search_used"] == 1 for row in known),
            "items_without_search": sum(row["response_status"] == "items" and row["search_used"] == 0 for row in known),
            "empty_with_search": sum(row["response_status"] == "zero_items" and row["search_used"] == 1 for row in known),
            "empty_without_search": sum(row["response_status"] == "zero_items" and row["search_used"] == 0 for row in known),
        })
    write_csv(source / "web_search_usage_per_request.csv", rows)
    write_csv(source / "web_search_usage_summary.csv", summary)
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / "output/random100_openai_gemini_comparison/openai")
    arguments = parser.parse_args()
    print(json.dumps(audit(arguments.source.resolve()), indent=2))
