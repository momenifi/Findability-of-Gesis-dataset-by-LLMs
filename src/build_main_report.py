import csv
from collections import defaultdict
from pathlib import Path


REPORT_DIR = Path("reports/model_comparison")
RUNS = {
    "OpenAI": Path("output/full_metadata_model_comparison"),
    "Gemini": Path("output/gemini_websearch"),
}
OPENWEBUI_ROOT = Path("output/provider_comparison/openwebui")
VARIANTS = {
    "V1": "v1_all_topics",
    "V2": "v2_single_topic",
    "V3": "v3_title_only",
    "V6": "v6_all_topics_abstract_natural_language",
}
FLAG_METRICS = {
    "strict_source": ("strict_source_hit_at_k_all_queries", "is_strict_source_dataset"),
    "source": ("source_hit_at_k_all_queries", "is_source_dataset"),
    "strict_gesis": ("strict_gesis_relevant_hit_at_k_all_queries", "is_strict_gesis_relevant_dataset"),
    "gesis": ("gesis_relevant_hit_at_k_all_queries", "is_gesis_relevant_dataset"),
}


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle, delimiter=";"))


def write_rows(path: Path, rows: list[dict], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter=";", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def value(rate: str, total: int) -> tuple[int, str]:
    numeric = float(rate or 0)
    return round(numeric * total), f"{numeric:.3f}"


def main() -> None:
    query_summary = []
    provider_summary = []
    loaded = {}

    for provider, root in RUNS.items():
        for variant, folder in VARIANTS.items():
            run = root / folder
            metrics = read_rows(run / "metrics_summary_audit.csv")[0]
            results = read_rows(run / "per_query_results.csv")
            queries = read_rows(run / "queries.csv")
            loaded[(provider, variant)] = (metrics, results, queries)
            total = int(metrics["requests"])
            source_datasets = len({row["source_dataset_id"] for row in queries})
            row = {
                "aggregation": "query_level", "provider": provider, "variant": variant,
                "queries": total, "source_datasets": source_datasets,
            }
            provider_row = {
                "variant": variant, "provider": provider, "model": metrics["model"],
                "requests": total,
            }
            statuses = read_rows(run / "metrics_response_status_audit.csv")
            provider_row["response_status"] = ", ".join(
                f"{status['response_status']}={status['count']}" for status in statuses
            )
            for label, (metric, _) in FLAG_METRICS.items():
                hits, rate = value(metrics[metric], total)
                row[f"{label}_hits"] = f"{hits} / {total}"
                row[f"{label}_hit_value"] = rate
                provider_row[f"{label}_hits"] = f"{hits} / {total}"
                provider_row[f"{label}_hit_value"] = rate
            title_hits, title_rate = value(metrics["title_gesis_relevant_hit_at_k_all_queries"], total)
            provider_row["title_gesis_hits"] = f"{title_hits} / {total}"
            provider_row["title_gesis_hit_value"] = title_rate
            query_summary.append(row)
            provider_summary.append(provider_row)

    comparison_fields = [
        "aggregation", "provider", "variant", "queries", "source_datasets",
        "strict_source_hits", "strict_source_hit_value", "source_hits", "source_hit_value",
        "strict_gesis_hits", "strict_gesis_hit_value", "gesis_hits", "gesis_hit_value",
    ]
    write_rows(REPORT_DIR / "openai_gemini_variant_comparison_summary.csv", query_summary, comparison_fields)

    openwebui_rows = []
    for variant in ("V1", "V6"):
        run = OPENWEBUI_ROOT / VARIANTS[variant]
        metrics = read_rows(run / "metrics_summary_audit.csv")[0]
        total = int(metrics["requests"])
        row = {
            "variant": variant, "provider": "OpenWebUI", "model": metrics["model"],
            "requests": total,
        }
        statuses = read_rows(run / "metrics_response_status_audit.csv")
        row["response_status"] = ", ".join(
            f"{status['response_status']}={status['count']}" for status in statuses
        )
        for label, (metric, _) in FLAG_METRICS.items():
            hits, metric_rate = value(metrics[metric], total)
            row[f"{label}_hits"] = f"{hits} / {total}"
            row[f"{label}_hit_value"] = metric_rate
        title_hits, title_rate = value(metrics["title_gesis_relevant_hit_at_k_all_queries"], total)
        row["title_gesis_hits"] = f"{title_hits} / {total}"
        row["title_gesis_hit_value"] = title_rate
        openwebui_rows.append(row)

    combined_provider = openwebui_rows + provider_summary
    write_rows(REPORT_DIR / "provider_variant_comparison_summary.csv", combined_provider, list(provider_summary[0]))

    strict_rows = []
    for row in openwebui_rows:
        strict_rows.append({
            "variant": row["variant"], "provider": row["provider"],
            "strict_source_hits": row["strict_source_hits"],
            "strict_source_hit_value": row["strict_source_hit_value"],
            "strict_gesis_hits": row["strict_gesis_hits"],
            "strict_gesis_hit_value": row["strict_gesis_hit_value"],
        })
    for row in query_summary:
        if row["variant"] in {"V1", "V3", "V6"}:
            strict_rows.append({
                "variant": row["variant"], "provider": row["provider"],
                "strict_source_hits": row["strict_source_hits"],
                "strict_source_hit_value": row["strict_source_hit_value"],
                "strict_gesis_hits": row["strict_gesis_hits"],
                "strict_gesis_hit_value": row["strict_gesis_hit_value"],
            })
    write_rows(REPORT_DIR / "provider_strict_source_gesis_summary.csv", strict_rows, list(strict_rows[0]))

    openai_rows = [row for row in query_summary if row["provider"] == "OpenAI" and row["variant"] != "V3"]
    for variant in ("V1", "V2", "V6"):
        _, results, queries = loaded[("OpenAI", variant)]
        source_ids = {row["source_dataset_id"] for row in queries}
        flags = defaultdict(lambda: defaultdict(bool))
        for result in results:
            source_id = result.get("source_dataset_id", "")
            for label, (_, column) in FLAG_METRICS.items():
                flags[source_id][label] |= result.get(column) == "1"
        total = len(source_ids)
        row = {
            "aggregation": "source_dataset_level", "provider": "OpenAI", "variant": variant,
            "queries": len(queries), "source_datasets": total,
        }
        for label in FLAG_METRICS:
            hits = sum(flags[source_id][label] for source_id in source_ids)
            row[f"{label}_hits"] = f"{hits} / {total}"
            row[f"{label}_hit_value"] = f"{hits / total:.3f}"
        openai_rows.append(row)
    openai_fields = [field for field in comparison_fields if field != "provider"]
    write_rows(REPORT_DIR / "openai_variant_comparison_summary.csv", openai_rows, openai_fields)

    output_targets = {
        ("Gemini", "V1"): "v1_gemini_outputs_labeled.csv",
        ("Gemini", "V2"): "v2_gemini_outputs_labeled.csv",
        ("Gemini", "V3"): "v3_gemini_outputs_labeled.csv",
        ("Gemini", "V6"): "v6_gemini_outputs_labeled.csv",
        ("OpenAI", "V3"): "v3_openai_outputs_labeled.csv",
    }
    output_fields = [
        "query_id", "query_variant", "mode", "model", "rank", "returned_title",
        "returned_url_or_doi", "matched_dataset_id", "match_method", "link_valid",
        "source_dataset_id", "is_source_dataset", "is_strict_source_dataset",
        "is_title_source_dataset", "is_gesis_relevant_dataset",
        "is_strict_gesis_relevant_dataset", "is_title_gesis_relevant_dataset",
        "title_identifier_conflict", "justification",
    ]
    for key, filename in output_targets.items():
        write_rows(REPORT_DIR / filename, loaded[key][1], output_fields)

    print(f"Updated main report files in {REPORT_DIR}")


if __name__ == "__main__":
    main()
