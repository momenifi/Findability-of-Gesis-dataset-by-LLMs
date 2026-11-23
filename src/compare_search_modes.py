"""Prepare or execute a paired OpenAI optional/required web-search experiment."""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import random
import subprocess
import sys
from types import SimpleNamespace
from uuid import uuid4

import pandas as pd
import yaml

from src.audit_results import classify_log, safe_model_name
from src.prompts import build_messages, format_messages
from src.run_pipeline import ROOT, fingerprint, read_yaml, resolve_config

DEFAULT_SOURCE = "output/random100_openai_gemini_comparison/openai/v3_title_only"
DEFAULT_IDS = "18,22,53,69,72,94"


def prepare(source_dir, ids, repeats, model, destination, conditions=("auto", "required")):
    if repeats < 1:
        raise ValueError("Repetitions must be positive")
    if not conditions or len(set(conditions)) != len(conditions) or not set(conditions) <= {"auto", "required"}:
        raise ValueError("Choose distinct search conditions: auto and/or required")
    queries_path = Path(source_dir) / "queries.csv"
    queries = pd.read_csv(queries_path, sep=";", keep_default_na=False)
    available = set(queries.query_id.astype(int))
    if not ids or not set(ids).issubset(available):
        raise ValueError(f"Unknown query IDs: {sorted(set(ids) - available)}")
    queries = queries[queries.query_id.astype(int).isin(ids)].copy()
    if queries.query_id.duplicated().any() or set(queries.query_variant) != {"V3_TITLE_ONLY"}:
        raise ValueError("Choose a V3 query file with unique query IDs")
    args = SimpleNamespace(provider="openai", sample="random100", variant="V3", template="title_original",
                           model=model, mode="WEB_SEARCH", limit=None, input_path=None, qrels_input_path=None)
    cfg = resolve_config(read_yaml(ROOT / "experiment.yaml"), args)
    for row in queries.itertuples(index=False):
        full = format_messages(build_messages(row.query_text, cfg["top_k_return"], "WEB_SEARCH", False))
        if getattr(row, "full_prompt_web_search", full) != full:
            raise ValueError(f"Saved prompt {row.query_id} differs from the current message builder")
    inputs = {key: fingerprint(cfg[key]) for key in ("input_path", "qrels_input_path")}
    destination = Path(destination).resolve()
    destination.mkdir(parents=True, exist_ok=False)
    runs = []
    for repeat in range(1, repeats + 1):
        # Paired prompt order is identical; alternate which condition runs first.
        ordered_ids = list(queries.query_id.astype(int))
        random.Random(42 + repeat).shuffle(ordered_ids)
        paired = queries.set_index("query_id").loc[ordered_ids].reset_index()
        for choice in (conditions if repeat % 2 else tuple(reversed(conditions))):
            directory = destination / f"repeat_{repeat:02d}_{choice}"
            directory.mkdir()
            settings = {**cfg, "output_dir": str(directory), "openai_web_search_tool_choice": choice}
            (directory / "resolved_config.yaml").write_text(yaml.safe_dump(settings, sort_keys=False), encoding="utf-8")
            paired.to_csv(directory / "queries.csv", sep=";", index=False)
            runs.append({"directory": directory.name, "repeat": repeat, "condition": choice})
    manifest = {"created_at": datetime.now(timezone.utc).isoformat(), "model": cfg["models_web"][0],
                "source_queries": fingerprint(queries_path), "inputs": inputs,
                "query_ids": list(queries.query_id.astype(int)), "repeats": repeats, "runs": runs,
                "note": "Selected historical failures: results do not estimate whole-corpus performance."}
    (destination / "comparison.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def summarize(destination):
    destination = Path(destination)
    manifest = json.loads((destination / "comparison.json").read_text(encoding="utf-8"))
    rows = []
    for run in manifest["runs"]:
        directory = destination / run["directory"]
        metric_path = directory / "metrics_per_query.csv"
        metrics = pd.read_csv(metric_path, sep=";") if metric_path.exists() else pd.DataFrame()
        for query_id in manifest["query_ids"]:
            path = directory / "logs" / f"query_{query_id}_WEB_SEARCH_{safe_model_name(manifest['model'])}.json"
            status, item_count = classify_log(path)
            data = json.loads(path.read_text(encoding="utf-8")) if path.exists() and status != "invalid_log_json" else {}
            attempts = data.get("attempts") or []
            final = attempts[-1].get("response") or {} if attempts else data
            calls = [item for item in final.get("output", []) if item.get("type") == "web_search_call"]
            search_count = sum((item.get("action") or {}).get("type") == "search" for item in calls)
            hits = metrics[metrics.query_id == query_id] if not metrics.empty else pd.DataFrame()
            rows.append({"repeat": run["repeat"], "condition": run["condition"], "query_id": query_id,
                         "status": status, "item_count": item_count, "has_items": int(status == "items"),
                         "search_used": int(search_count > 0), "search_actions": search_count,
                         "web_tool_calls": len(calls), "attempts": len(attempts),
                         "response_model": final.get("model", ""),
                         "evaluation_available": int(not hits.empty),
                         "strict_source_hit": float(hits.iloc[0].strict_source_hit_at_k) if not hits.empty else 0.0,
                         "empty_answer": int(status == "zero_items"), "api_error": int(status == "api_error"),
                         "missing_log": int(status == "missing_log")})
    frame = pd.DataFrame(rows)
    frame.to_csv(destination / "comparison_per_request.csv", sep=";", index=False)
    summary = frame.groupby("condition", sort=False).agg(
        requests=("query_id", "count"), requests_with_search=("search_used", "sum"),
        search_rate=("search_used", "mean"), responses_with_items=("has_items", "sum"),
        empty_answers=("empty_answer", "sum"), api_errors=("api_error", "sum"),
        missing_logs=("missing_log", "sum"), evaluated_requests=("evaluation_available", "sum"),
        strict_source_hits=("strict_source_hit", "sum"), strict_source_hit_rate=("strict_source_hit", "mean"),
    ).reset_index()
    summary.to_csv(destination / "comparison_summary.csv", sep=";", index=False)
    print(summary.to_string(index=False), flush=True)
    return summary


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source-run", default=DEFAULT_SOURCE)
    ap.add_argument("--query-ids", default=DEFAULT_IDS)
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--conditions", nargs="+", choices=("auto", "required"), default=["auto", "required"])
    ap.add_argument("--model", help="Same model for both conditions; defaults to the OpenAI profile")
    ap.add_argument("--execute", action="store_true", help="Make paid API calls and evaluate both conditions")
    ap.add_argument("--summarize", help="Summarize a prepared comparison directory without API calls")
    args = ap.parse_args()
    if args.summarize:
        summarize(ROOT / args.summarize)
        return
    try:
        ids = sorted({int(value.strip()) for value in args.query_ids.split(",") if value.strip()})
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        destination = ROOT / "output" / "search_mode_comparison" / f"{stamp}_{uuid4().hex[:8]}"
        manifest = prepare(ROOT / args.source_run, ids, args.repeats, args.model, destination, args.conditions)
    except ValueError as exc:
        ap.error(str(exc))
    count = len(ids) * args.repeats * len(args.conditions)
    print(f"Prepared {count} planned requests: {len(ids)} prompts x {args.repeats} repeats x {len(args.conditions)} conditions.", flush=True)
    print(f"Model: {manifest['model']}\nResults: {destination}", flush=True)
    if not args.execute:
        print("Preparation only. No API calls made. Add --execute to start a new comparison.")
        return
    if not os.environ.get("OPENAI_API_KEY"):
        ap.error("Set OPENAI_API_KEY before executing")
    for run in manifest["runs"]:
        directory = destination / run["directory"]
        for stage in ("run_llm", "match_and_eval", "audit_results"):
            print(f"Repeat {run['repeat']} / {run['condition']} / {stage}", flush=True)
            code = subprocess.run([sys.executable, "-m", f"src.{stage}", "--config", str(directory / "resolved_config.yaml")], cwd=ROOT).returncode
            if code:
                summarize(destination)
                raise SystemExit(code)
    summarize(destination)


if __name__ == "__main__":
    main()
