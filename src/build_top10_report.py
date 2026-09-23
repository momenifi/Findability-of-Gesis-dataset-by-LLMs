import csv
from pathlib import Path


REPORT_DIR = Path("reports/model_comparison")
RUNS = {
    "OpenAI": Path("output/top10_visibility/requested_openai"),
    "Gemini": Path("output/top10_visibility/requested_gemini"),
}
VARIANTS = {
    "V1": "v1_all_topics",
    "V2": "v2_single_topic",
    "V3": "v3_title_only",
    "V6": "v6_all_topics_abstract_natural_language",
}
OUTPUT_COLUMNS = [
    "query_id", "query_variant", "mode", "model", "rank", "returned_title",
    "returned_url_or_doi", "matched_dataset_id", "match_method", "link_valid",
    "title_matched_dataset_id", "title_match_score", "title_match_method",
    "title_identifier_conflict", "is_strict_source_dataset", "is_source_dataset",
    "is_title_source_dataset", "is_strict_gesis_relevant_dataset",
    "is_gesis_relevant_dataset", "is_title_gesis_relevant_dataset",
    "source_dataset_id",
]


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle, delimiter=";"))


def write_rows(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter=";", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def rate(value: str) -> float:
    return round(float(value or 0), 3)


def main() -> None:
    summaries = []
    statuses = []
    conflicts = []
    outputs = []
    queries = []

    for provider, root in RUNS.items():
        for variant, folder in VARIANTS.items():
            run = root / folder
            metrics = read_rows(run / "metrics_summary_audit.csv")[0]
            result_rows = read_rows(run / "per_query_results.csv")
            query_rows = read_rows(run / "queries.csv")
            requests = int(metrics["requests"])
            conflict_ids = {
                row["query_id"] for row in result_rows
                if row.get("title_identifier_conflict") == "1"
            }
            conflict_rows = sum(
                row.get("title_identifier_conflict") == "1" for row in result_rows
            )

            def hits(metric: str) -> int:
                return round(float(metrics.get(metric, 0) or 0) * requests)

            summary = {
                "provider": provider,
                "variant": variant,
                "queries": requests,
                "responses_with_items": int(metrics["responses_with_items"]),
                "coverage": rate(metrics["coverage_rate"]),
                "strict_source_hits": hits("strict_source_hit_at_k_all_queries"),
                "strict_source_rate": rate(metrics["strict_source_hit_at_k_all_queries"]),
                "source_hits": hits("source_hit_at_k_all_queries"),
                "source_rate": rate(metrics["source_hit_at_k_all_queries"]),
                "title_source_hits": hits("title_source_hit_at_k_all_queries"),
                "title_source_rate": rate(metrics["title_source_hit_at_k_all_queries"]),
                "strict_gesis_hits": hits("strict_gesis_relevant_hit_at_k_all_queries"),
                "strict_gesis_rate": rate(metrics["strict_gesis_relevant_hit_at_k_all_queries"]),
                "gesis_hits": hits("gesis_relevant_hit_at_k_all_queries"),
                "gesis_rate": rate(metrics["gesis_relevant_hit_at_k_all_queries"]),
                "title_identifier_conflict_queries": len(conflict_ids),
                "title_identifier_conflict_query_rate": round(len(conflict_ids) / requests, 3),
                "title_identifier_conflict_rows": conflict_rows,
            }
            summaries.append(summary)
            statuses.append({key: summary[key] for key in (
                "provider", "variant", "queries", "responses_with_items", "coverage"
            )})
            conflicts.append({key: summary[key] for key in (
                "provider", "variant", "queries", "title_identifier_conflict_queries",
                "title_identifier_conflict_query_rate", "title_identifier_conflict_rows"
            )})
            outputs.extend({"provider": provider, "variant_short": variant, **row} for row in result_rows)
            queries.extend({"provider": provider, "variant_short": variant, **row} for row in query_rows)

    summary_fields = list(summaries[0])
    write_rows(REPORT_DIR / "top10_provider_variant_summary.csv", summaries, summary_fields)
    write_rows(REPORT_DIR / "top10_provider_response_status.csv", statuses, list(statuses[0]))
    write_rows(REPORT_DIR / "top10_provider_title_identifier_conflicts.csv", conflicts, list(conflicts[0]))
    write_rows(REPORT_DIR / "top10_provider_outputs_labeled.csv", outputs, ["provider", "variant_short", *OUTPUT_COLUMNS])
    query_fields = ["provider", "variant_short", *read_rows(next(iter(RUNS.values())) / next(iter(VARIANTS.values())) / "queries.csv")[0].keys()]
    write_rows(REPORT_DIR / "top10_provider_queries.csv", queries, query_fields)
    print(f"Updated top-10 report files in {REPORT_DIR}")


if __name__ == "__main__":
    main()
