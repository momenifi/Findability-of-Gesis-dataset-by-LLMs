"""Test optional/required OpenWebUI tool choice on one saved title prompt."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from uuid import uuid4

import pandas as pd
import requests

from src.prompts import build_messages, format_messages
from src.run_llm import _build_openwebui_payload, _openwebui_chat_endpoint, get_api_key, load_config, _redact_secrets


ROOT = Path(__file__).resolve().parents[1]


def classify(body):
    choice = (body.get("choices") or [{}])[0]
    message = choice.get("message") or {}
    calls = [call.get("function", {}).get("name", "") for call in message.get("tool_calls", [])]
    sources = bool(body.get("sources") or body.get("citations") or message.get("sources") or message.get("citations"))
    status = "unresolved_tool_calls" if calls else "answer_with_source_metadata" if sources else "answer_without_search_execution_evidence"
    return {"outcome": status, "finish_reason": choice.get("finish_reason", ""),
            "content_present": bool(message.get("content")), "requested_tools": calls,
            "source_metadata_present": sources,
            "note": "A tool call requests execution; it is not evidence the search was executed."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "config_openwebui.yaml")
    parser.add_argument("--model")
    parser.add_argument("--query-id", type=int, default=18)
    parser.add_argument("--web-mode", choices=("features", "tool_ids"), default="features")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    cfg = load_config(str(args.config))
    cfg["openwebui_web_search_mode"] = args.web_mode
    model = args.model or cfg["models_web"][0]
    queries = pd.read_csv(ROOT / "output/current_results_sources/openai/random100/v3_title_only/queries.csv", sep=";", keep_default_na=False)
    selected = queries[queries.query_id == args.query_id]
    if len(selected) != 1:
        parser.error("Choose a saved V3 query ID")
    row = selected.iloc[0]
    messages = build_messages(row.query_text, cfg.get("top_k_return", 10), "WEB_SEARCH", False)
    if row.full_prompt_web_search != format_messages(messages):
        parser.error("Saved prompt differs from message builder")
    endpoint = _openwebui_chat_endpoint(cfg)
    print(f"Model: {model}\nEndpoint: {endpoint}\nQuery: {args.query_id}\nWeb mode: {args.web_mode}", flush=True)
    if not args.execute:
        print("Preview only. Add --execute for two requests: auto and required.")
        return
    key = get_api_key(cfg)
    directory = ROOT / "output/archive/openwebui_required_diagnostics" / (
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_" + uuid4().hex[:8])
    directory.mkdir(parents=True)

    def safe(value):
        return _redact_secrets(json.dumps(value, indent=2, ensure_ascii=True).replace(key, "<REDACTED>"))

    for condition in ("auto", "required"):
        payload = _build_openwebui_payload({**cfg, "openwebui_tool_choice": condition}, model, messages, True)
        record = {"condition": condition, "query_id": args.query_id, "request": payload, "endpoint": endpoint}
        print(f"Testing {condition}...", flush=True)
        try:
            response = requests.post(endpoint, headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                                     json=payload, timeout=(15, 90))
            record["http_status"] = response.status_code
            try:
                body = response.json()
            except ValueError:
                body = {"unparsed_response": response.text}
            record["response"] = body
            record["classification"] = classify(body) if response.ok else {"outcome": "api_error"}
            print(safe({"http_status": response.status_code, **record["classification"]}), flush=True)
            if not response.ok:
                print(safe(body), flush=True)
        except requests.RequestException as exc:
            record["transport_error"] = str(exc)
            print(safe({"transport_error": str(exc)}), flush=True)
        (directory / f"{condition}.json").write_text(safe(record), encoding="utf-8")
    print(f"Saved requests and raw responses: {directory}", flush=True)


if __name__ == "__main__":
    main()
