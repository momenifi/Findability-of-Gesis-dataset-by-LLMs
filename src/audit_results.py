import argparse
import json
import re
from pathlib import Path

import pandas as pd
import yaml

from .config_paths import resolve_output_dir

OUTPUT_CSV_SEP = ";"


def load_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def safe_model_name(model: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(model))


def extract_json(text: str) -> dict:
    try:
        return json.loads(text)
    except Exception:
        pass
    if not text:
        raise ValueError("Empty response text")
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("No JSON object found")
    return json.loads(text[start : end + 1])


def configured_models(cfg: dict) -> dict[str, list[str]]:
    def as_list(value) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        text = str(value).strip()
        return [text] if text else []

    return {
        "NO_WEB": as_list(cfg.get("models_no_web", cfg.get("model_no_web"))),
        "WEB_SEARCH": as_list(cfg.get("models_web", cfg.get("model_web"))),
    }


def classify_log(path: Path) -> tuple[str, int]:
    if not path.exists():
        return "missing_log", 0

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return "invalid_log_json", 0

    if isinstance(data, dict) and data.get("error"):
        return "api_error", 0

    choices = data.get("choices") if isinstance(data, dict) else None
    if not choices:
        return "empty_response", 0

    message = choices[0].get("message") or {}
    content = message.get("content")
    tool_calls = message.get("tool_calls") or []

    if (content is None or str(content).strip() == "") and tool_calls:
        return "tool_calls_only", 0
    if content is None or str(content).strip() == "":
        return "empty_content", 0

    try:
        parsed = extract_json(str(content))
    except Exception:
        return "invalid_content_json", 0

    raw_items = parsed.get("items", []) if isinstance(parsed, dict) else []
    if not isinstance(raw_items, list):
        return "invalid_items", 0
    if not raw_items:
        return "zero_items", 0
    return "items", len(raw_items)


def audit(config_path: str) -> None:
    cfg = load_config(config_path)
    output_dir = resolve_output_dir(cfg)
    queries_path = output_dir / "queries.csv"
    metrics_path = output_dir / "metrics_per_query.csv"
    per_query_path = output_dir / "per_query_results.csv"
    logs_dir = output_dir / "logs"

    if not queries_path.exists():
        raise FileNotFoundError(f"{queries_path} not found")
    if not metrics_path.exists():
        raise FileNotFoundError(f"{metrics_path} not found")

    queries = pd.read_csv(queries_path, sep=None, engine="python")
    metrics = pd.read_csv(metrics_path, sep=None, engine="python")
    per_query = pd.read_csv(per_query_path, sep=None, engine="python") if per_query_path.exists() else pd.DataFrame()
    top_k = int(cfg.get("top_k_return", 10))

    metric_by_key = {
        (int(row.query_id), str(row.mode), str(row.model)): row
        for row in metrics.itertuples(index=False)
    }

    exact_hit_keys = set()
    fuzzy_hit_keys = set()
    if not per_query.empty:
        relevant = per_query[per_query["is_relevant"].astype(str) == "1"]
        for row in relevant.itertuples(index=False):
            key = (int(row.query_id), str(row.mode), str(row.model))
            if float(row.match_confidence) >= 1.0:
                exact_hit_keys.add(key)
            else:
                fuzzy_hit_keys.add(key)

    request_rows = []
    models_by_mode = configured_models(cfg)
    modes = [str(mode).strip().upper() for mode in cfg.get("modes", ["NO_WEB"]) if str(mode).strip()]
    for query in queries.itertuples(index=False):
        query_id = int(query.query_id)
        query_variant = str(query.query_variant)
        for mode in modes:
            for model in models_by_mode.get(mode, []):
                safe_model = safe_model_name(model)
                log_path = logs_dir / f"query_{query_id}_{mode}_{safe_model}.json"
                status, item_count = classify_log(log_path)
                metric = metric_by_key.get((query_id, mode, model))
                key = (query_id, mode, model)
                request_rows.append(
                    {
                        "query_id": query_id,
                        "query_variant": query_variant,
                        "mode": mode,
                        "model": model,
                        "response_status": status,
                        "item_count": item_count,
                        "has_items": int(status == "items"),
                        "hit_at_k_all": float(metric.hit_at_k) if metric is not None else 0.0,
                        "mrr_all": float(metric.mrr) if metric is not None else 0.0,
                        "ndcg_at_k_all": float(metric.ndcg_at_k) if metric is not None else 0.0,
                        "recall_at_k_all": float(metric.recall_at_k) if metric is not None else 0.0,
                        "precision_at_k_all": float(metric.precision_at_k) if metric is not None else 0.0,
                        "exact_hit_at_k_all": int(key in exact_hit_keys),
                        "fuzzy_hit_at_k_all": int(key in fuzzy_hit_keys and key not in exact_hit_keys),
                        "log_path": str(log_path),
                    }
                )

    audit_per_request = pd.DataFrame(request_rows)
    group_cols = ["query_variant", "mode", "model"]
    summary = (
        audit_per_request.groupby(group_cols, sort=False)
        .agg(
            requests=("query_id", "count"),
            responses_with_items=("has_items", "sum"),
            coverage_rate=("has_items", "mean"),
            hit_at_k_all_queries=("hit_at_k_all", "mean"),
            mrr_all_queries=("mrr_all", "mean"),
            ndcg_at_k_all_queries=("ndcg_at_k_all", "mean"),
            recall_at_k_all_queries=("recall_at_k_all", "mean"),
            precision_at_k_all_queries=("precision_at_k_all", "mean"),
            exact_hit_at_k_all_queries=("exact_hit_at_k_all", "mean"),
            fuzzy_hit_at_k_all_queries=("fuzzy_hit_at_k_all", "mean"),
        )
        .reset_index()
    )

    status_summary = (
        audit_per_request.groupby(group_cols + ["response_status"], sort=False)
        .size()
        .reset_index(name="count")
    )

    audit_per_request.to_csv(output_dir / "metrics_audit_per_request.csv", index=False, sep=OUTPUT_CSV_SEP)
    summary.to_csv(output_dir / "metrics_summary_audit.csv", index=False, sep=OUTPUT_CSV_SEP)
    status_summary.to_csv(output_dir / "metrics_response_status_audit.csv", index=False, sep=OUTPUT_CSV_SEP)

    print(f"Wrote {output_dir / 'metrics_summary_audit.csv'}")
    print(f"Wrote {output_dir / 'metrics_audit_per_request.csv'}")
    print(f"Wrote {output_dir / 'metrics_response_status_audit.csv'}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, help="Path to config.yaml")
    args = parser.parse_args()
    audit(args.config)


if __name__ == "__main__":
    main()
