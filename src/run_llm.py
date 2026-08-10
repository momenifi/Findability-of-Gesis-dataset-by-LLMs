import argparse
import copy
import json
import os
import re
import time
from pathlib import Path
from typing import List

import pandas as pd
import requests
import yaml
from openai import OpenAI

from .load_metadata import load_metadata
from .config_paths import apply_variant_override, resolve_output_dir
from .prompts import build_messages

OUTPUT_CSV_SEP = ";"


def load_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _as_list(value) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    return [text] if text else []


def get_api_key(cfg: dict) -> str | None:
    api_key_env = cfg.get("api_key_env")
    if not api_key_env:
        return None
    api_key = os.getenv(api_key_env)
    if not api_key:
        raise SystemExit(f"Set {api_key_env} in your environment first.")
    return api_key


def _is_openwebui(cfg: dict) -> bool:
    base_url = str(cfg.get("api_base_url") or "").lower()
    api_key_env = str(cfg.get("api_key_env") or "").lower()
    return "openwebui" in base_url or api_key_env == "openwebui_api_key"


def _openwebui_chat_endpoint(cfg: dict) -> str:
    base_url = str(cfg.get("api_base_url") or "").rstrip("/")
    if base_url.endswith("/api"):
        return f"{base_url}/chat/completions"
    return f"{base_url}/api/chat/completions"


def _content_to_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        texts = []
        for part in content:
            if isinstance(part, dict):
                text = part.get("text") or part.get("content")
                if isinstance(text, str):
                    texts.append(text)
        return "\n".join(texts)
    return ""


def _response_text(response) -> str:
    if isinstance(response, dict):
        choices = response.get("choices") or []
        if choices:
            message = choices[0].get("message") or {}
            return _content_to_text(message.get("content"))
        return ""
    if getattr(response, "output_text", None):
        return response.output_text
    if getattr(response, "choices", None):
        try:
            return _content_to_text(response.choices[0].message.content)
        except Exception:
            return ""
    return ""


def _tool_call_names(response) -> List[str]:
    if not isinstance(response, dict):
        return []
    choices = response.get("choices") or []
    if not choices:
        return []
    message = choices[0].get("message") or {}
    names = []
    for tool_call in message.get("tool_calls") or []:
        function = tool_call.get("function") or {}
        name = function.get("name")
        if name:
            names.append(str(name))
    return names


def _extract_json(text: str) -> dict:
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


def _extract_items(parsed) -> List[dict]:
    if isinstance(parsed, list):
        raw_items = parsed
    elif isinstance(parsed, dict):
        raw_items = parsed.get("items", [])
        if not isinstance(raw_items, list) and parsed.get("title"):
            raw_items = [parsed]
    else:
        raw_items = []

    items = []
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or item.get("study_title") or item.get("name") or "").strip()
        url_or_doi = str(
            item.get("url_or_doi")
            or item.get("doi")
            or item.get("gesis_url")
            or item.get("landing_page")
            or item.get("url")
            or item.get("link")
            or ""
        ).strip()
        justification = str(item.get("justification") or item.get("reason") or item.get("explanation") or "").strip()
        if title or url_or_doi:
            items.append({"title": title, "url_or_doi": url_or_doi, "justification": justification})
    return items


def _serialize_response(response) -> str:
    if isinstance(response, (dict, list)):
        return json.dumps(response, indent=2, ensure_ascii=False)
    if hasattr(response, "model_dump_json"):
        return response.model_dump_json(indent=2)
    try:
        return json.dumps(response, default=str, indent=2, ensure_ascii=False)
    except Exception:
        return str(response)


def _response_to_json_value(response):
    if isinstance(response, (dict, list)) or response is None:
        return response
    if hasattr(response, "model_dump"):
        try:
            return response.model_dump(mode="json")
        except Exception:
            pass
    try:
        return json.loads(_serialize_response(response))
    except Exception:
        return {"unserializable_response": str(response)}


def _call_openwebui_chat(cfg: dict, model: str, messages: List[dict], enable_web_search: bool) -> dict:
    payload = {"model": model, "messages": messages}
    if enable_web_search:
        web_search_mode = str(cfg.get("openwebui_web_search_mode", "tool_ids")).strip().lower()
        if web_search_mode == "features":
            payload["features"] = {"web_search": True}
        elif web_search_mode == "tool_ids":
            payload["tool_ids"] = ["web_search"]
        else:
            raise ValueError(f"Unsupported openwebui_web_search_mode: {web_search_mode}")

    # GESIS OpenWebUI binds knowledge-base tools (search_knowledge_files,
    # query_knowledge_files, ...) to some model configs server-side. Reasoning
    # models (gpt-5, gpt-5.4, ...) call those instead of answering, returning
    # content=null with finish_reason=tool_calls. tool_choice="none" forbids the
    # model from emitting any function call, forcing it to answer from the
    # already-injected context; it does NOT disable OpenWebUI's server-side web
    # search. Set openwebui_tool_choice to "auto" to restore the old behavior.
    tool_choice = str(cfg.get("openwebui_tool_choice", "none")).strip()
    if tool_choice and tool_choice.lower() != "auto":
        payload["tool_choice"] = tool_choice

    headers = {
        "Authorization": f"Bearer {get_api_key(cfg)}",
        "Content-Type": "application/json",
    }
    response = requests.post(
        _openwebui_chat_endpoint(cfg),
        headers=headers,
        json=payload,
        timeout=(
            float(cfg.get("request_timeout_connect_seconds", 30)),
            float(cfg.get("request_timeout_read_seconds", 600)),
        ),
    )
    response.raise_for_status()
    return response.json()


def _call_openai(cfg: dict, model: str, messages: List[dict], enable_web_search: bool):
    client = OpenAI(base_url=cfg.get("api_base_url") or None, api_key=get_api_key(cfg))
    if enable_web_search:
        return client.responses.create(
            model=model,
            input=messages,
            tools=[{"type": "web_search"}],
        )
    return client.chat.completions.create(model=model, messages=messages)


def run_llm(config_path: str, variant: str | None = None) -> pd.DataFrame:
    cfg = apply_variant_override(load_config(config_path), variant)
    output_dir = resolve_output_dir(cfg)
    output_dir.mkdir(parents=True, exist_ok=True)
    logs_dir = output_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    queries_path = output_dir / "queries.csv"
    if not queries_path.exists():
        raise FileNotFoundError(f"{queries_path} not found. Run generate_queries first.")

    queries = pd.read_csv(queries_path, sep=None, engine="python")
    # Keep this load for validation/future candidate filtering.
    load_metadata(cfg["input_path"], cfg["input_format"])

    modes = [str(mode).strip().upper() for mode in cfg.get("modes", ["NO_WEB"]) if str(mode).strip()]
    models_by_mode = {
        "NO_WEB": _as_list(cfg.get("models_no_web", cfg.get("model_no_web"))),
        "WEB_SEARCH": _as_list(cfg.get("models_web", cfg.get("model_web"))),
    }
    top_k = int(cfg.get("top_k_return", 10))
    include_top_k_limit = bool(cfg.get("include_top_k_limit_in_prompt", True))
    max_returned_items_to_save = int(cfg.get("max_returned_items_to_save", 0) or 0)
    total_requests = sum(len(queries) * len(models_by_mode.get(mode, [])) for mode in modes)
    max_retries = int(cfg.get("request_max_retries", 2))
    retry_backoff_seconds = float(cfg.get("request_retry_backoff_seconds", 5))
    use_openwebui_native = _is_openwebui(cfg)

    results_path = output_dir / "llm_results.csv"
    if results_path.exists():
        results_path.unlink()

    rows = []
    completed_requests = 0

    for _, query in queries.iterrows():
        query_id = int(query["query_id"])
        query_variant = str(query["query_variant"])
        query_text = str(query["query_text"]) if not pd.isna(query["query_text"]) else ""

        for mode in modes:
            for model in models_by_mode.get(mode, []):
                messages = build_messages(query_text, top_k, mode, include_top_k_limit)
                parsed = None
                last_response = None
                attempt_traces = []

                for attempt in range(max_retries + 1):
                    attempt_trace = {
                        "attempt": attempt + 1,
                        "request": {
                            "model": model,
                            "mode": mode,
                            "web_search_enabled": mode == "WEB_SEARCH",
                            "openwebui_web_search_mode": (
                                str(cfg.get("openwebui_web_search_mode", "tool_ids"))
                                if use_openwebui_native and mode == "WEB_SEARCH"
                                else None
                            ),
                            "messages": copy.deepcopy(messages),
                        },
                    }
                    print(
                        f"START [{completed_requests + 1}/{total_requests}] "
                        f"query_id={query_id} variant={query_variant} mode={mode} "
                        f"model={model} attempt={attempt + 1}",
                        flush=True,
                    )
                    try:
                        if use_openwebui_native:
                            last_response = _call_openwebui_chat(
                                cfg=cfg,
                                model=model,
                                messages=messages,
                                enable_web_search=(mode == "WEB_SEARCH"),
                            )
                        else:
                            last_response = _call_openai(
                                cfg=cfg,
                                model=model,
                                messages=messages,
                                enable_web_search=(mode == "WEB_SEARCH"),
                            )
                    except Exception as exc:
                        last_response = {
                            "error": str(exc),
                            "query_id": query_id,
                            "query_variant": query_variant,
                            "mode": mode,
                            "model": model,
                            "attempt": attempt + 1,
                        }
                        attempt_trace["response"] = last_response
                        attempt_traces.append(attempt_trace)
                        if attempt < max_retries:
                            wait_seconds = retry_backoff_seconds * (attempt + 1)
                            print(
                                f"RETRY query_id={query_id} variant={query_variant} mode={mode} "
                                f"model={model} after error: {exc} (sleep {wait_seconds:.1f}s)",
                                flush=True,
                            )
                            time.sleep(wait_seconds)
                            continue
                        break

                    attempt_trace["response"] = _response_to_json_value(last_response)
                    attempt_traces.append(attempt_trace)

                    try:
                        parsed = _extract_json(_response_text(last_response))
                        break
                    except Exception:
                        if attempt < max_retries:
                            tool_names = _tool_call_names(last_response)
                            if tool_names:
                                retry_note = (
                                    f"Your last response only contained tool calls ({', '.join(tool_names)}) "
                                    "and no final JSON content. Do not call time/date tools. "
                                )
                            else:
                                retry_note = "Your last response was invalid. "
                            messages.append(
                                {
                                    "role": "user",
                                    "content": (
                                        retry_note
                                        + "Return ONLY valid JSON in this exact shape: "
                                        '{"items":[{"title":"...","url_or_doi":"...","justification":"..."}]}.'
                                    ),
                                }
                            )
                            continue

                if parsed is None:
                    parsed = {"items": []}

                safe_model = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(model))
                raw_path = logs_dir / f"query_{query_id}_{mode}_{safe_model}.json"
                log_record = {
                    "query_id": query_id,
                    "query_variant": query_variant,
                    "mode": mode,
                    "model": model,
                    "top_k_return": top_k,
                    "include_top_k_limit_in_prompt": include_top_k_limit,
                    "max_returned_items_to_save": max_returned_items_to_save,
                    "attempts": attempt_traces,
                }
                raw_path.write_text(
                    json.dumps(log_record, indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )

                items = _extract_items(parsed)
                saved_items = items if max_returned_items_to_save <= 0 else items[:max_returned_items_to_save]
                batch_rows = []
                for rank, item in enumerate(saved_items, start=1):
                    record = {
                        "query_id": query_id,
                        "query_variant": query_variant,
                        "mode": mode,
                        "model": model,
                        "rank": rank,
                        "returned_title": str(item.get("title", "")),
                        "returned_url_or_doi": str(item.get("url_or_doi", "")),
                        "justification": str(item.get("justification", "")),
                        "raw_response_path": str(raw_path),
                    }
                    rows.append(record)
                    batch_rows.append(record)

                if batch_rows:
                    pd.DataFrame(batch_rows).to_csv(
                        results_path,
                        mode="a",
                        header=not results_path.exists(),
                        index=False,
                        sep=OUTPUT_CSV_SEP,
                    )

                completed_requests += 1
                print(
                    f"[{completed_requests}/{total_requests}] "
                    f"query_id={query_id} variant={query_variant} mode={mode} "
                    f"model={model} items={len(saved_items)}",
                    flush=True,
                )

    out = pd.DataFrame(rows)
    if not results_path.exists():
        out.to_csv(results_path, index=False, sep=OUTPUT_CSV_SEP)
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, help="Path to config.yaml")
    parser.add_argument("-V", "--variant", help="Override query variant (V1, V2, V3, V4, V5, or V6)")
    args = parser.parse_args()
    run_llm(args.config, args.variant)


if __name__ == "__main__":
    main()
