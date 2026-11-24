"""Inspect exact Gemini search payloads and grounding for a few saved prompts."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from uuid import uuid4

import pandas as pd
import requests

from scripts.audit_gemini_search_usage import grounding_evidence
from scripts.audit_openai_search_usage import write_csv
from src.prompts import build_messages, format_messages
from src.run_llm import _build_gemini_payload, _gemini_generate_content_endpoint, _redact_secrets, _response_text, load_config


ROOT = Path(__file__).resolve().parents[1]


def diagnose(config_path, source, ids, execute=False, output_root=None):
    cfg = load_config(str(config_path))
    model = cfg["models_web"][0]
    queries = pd.read_csv(source / "queries.csv", sep=";", keep_default_na=False)
    selected = queries[queries.query_id.astype(int).isin(ids)]
    if not ids or set(selected.query_id.astype(int)) != set(ids) or selected.query_id.duplicated().any():
        raise ValueError("Choose existing, unique query IDs")
    planned = []
    for row in selected.itertuples(index=False):
        messages = build_messages(row.query_text, cfg.get("top_k_return", 10), "WEB_SEARCH", False)
        if getattr(row, "full_prompt_web_search", format_messages(messages)) != format_messages(messages):
            raise ValueError(f"Saved full prompt differs from current builder: {row.query_id}")
        planned.append((int(row.query_id), _build_gemini_payload(messages, True)))
    key = os.environ.get(cfg.get("api_key_env", "GEMINI_API_KEY"), "")
    if execute and not key:
        raise ValueError("Set GEMINI_API_KEY in this terminal first")

    def safe(value):
        text = json.dumps(value, indent=2, ensure_ascii=True)
        return _redact_secrets(text.replace(key, "<REDACTED>") if key else text)

    endpoint = _gemini_generate_content_endpoint(cfg, model)
    print(f"Model: {model}\nEndpoint: {_redact_secrets(endpoint)}", flush=True)
    for query_id, payload in planned:
        print(f"Query {query_id}: outgoing JSON payload\n{safe(payload)}", flush=True)
    if not execute:
        print("Preview only; no files written or API calls made. Add --execute for paid requests.")
        return None
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    destination = (output_root or ROOT / "output/archive/gemini_search_diagnostics") / f"{stamp}_{uuid4().hex[:8]}"
    destination.mkdir(parents=True, exist_ok=False)
    manifest = {"model": model, "query_ids": ids, "source_queries": str(source / "queries.csv"),
                "queries_sha256": hashlib.sha256((source / "queries.csv").read_bytes()).hexdigest(),
                "note": "Fresh diagnostic only; no retries or changes to original results."}
    (destination / "manifest.json").write_text(safe(manifest), encoding="utf-8")
    summaries = []
    for query_id, payload in planned:
        record = {"query_id": query_id, "endpoint": endpoint, "request_payload": payload}
        failed = False
        try:
            response = requests.post(endpoint, params={"key": key}, json=payload,
                                     headers={"Content-Type": "application/json"},
                                     timeout=(float(cfg.get("request_timeout_connect_seconds", 30)),
                                              float(cfg.get("request_timeout_read_seconds", 600))))
            record["http_status"] = response.status_code
            try:
                body = response.json()
            except ValueError:
                body = {"unparsed_response": response.text}
            record["response"] = body
            failed = not response.ok
            evidence = grounding_evidence(body)
            summaries.append({"query_id": query_id, "http_status": response.status_code, **evidence})
            print(f"Query {query_id}: HTTP {response.status_code}\nGrounding evidence: {safe(evidence)}", flush=True)
            print(f"Assistant text:\n{_response_text(body)}".replace(key, "<REDACTED>"), flush=True)
            if failed:
                print(f"API error:\n{safe(body)}", flush=True)
        except requests.RequestException as exc:
            record["transport_error"] = str(exc)
            summaries.append({"query_id": query_id, "http_status": "", **{k: "" for k in grounding_evidence({})}})
            print(f"Request failed: {safe(str(exc))}", flush=True)
            failed = True
        (destination / f"query_{query_id}.json").write_text(safe(record), encoding="utf-8")
        write_csv(destination / "summary.csv", summaries)
        if failed:
            print("Stopped after error; no automatic retries.", flush=True)
            break
    print(f"Full payloads and raw responses: {destination}", flush=True)
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "output/current_results_sources/gemini/random100/v3_title_only/config.yaml")
    parser.add_argument("--source-run", type=Path, default=ROOT / "output/current_results_sources/gemini/random100/v3_title_only")
    parser.add_argument("--query-ids", default="1,18,53")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    try:
        ids = sorted({int(value.strip()) for value in args.query_ids.split(",") if value.strip()})
        diagnose(args.config, args.source_run, ids, args.execute)
    except ValueError as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
