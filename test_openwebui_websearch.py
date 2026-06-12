import csv
import json
import os
from pathlib import Path

import requests


BASE_URL = os.getenv("OPENWEBUI_BASE_URL", "https://ai-openwebui.gesis.org").rstrip("/")
API_KEY = os.getenv("OPENWEBUI_API_KEY")

MODELS = [
    "gemma3:27b",
    "gpt-4.1",
    "gpt-4.1-mini",
    "llama4:latest",
    "o4-mini",
    "gpt-5",
    "gpt-5-mini",
    "gpt-5.1",
    "gpt-5.4",
    "gpt-oss:120b",
    "gpt-oss:latest",
    "mistral-small3.2:latest",
]

TEST_MODEL = os.getenv("OPENWEBUI_TEST_MODEL")
if TEST_MODEL:
    MODELS = [TEST_MODEL]

OUT_PATH = Path("openwebui_websearch_model_check.csv")

PROMPT = (
    "Use web search if available. Find the GESIS dataset titled "
    "'Federal Parliament Election 1972 (Panel: 2nd Wave, October 1971 - January 1972)'. "
    'Return ONLY JSON: {"items":[{"title":"...","url_or_doi":"..."}]}'
)


if not API_KEY:
    raise SystemExit("Set OPENWEBUI_API_KEY in your environment first.")


def classify_response(response: requests.Response) -> dict:
    result = {
        "status_code": response.status_code,
        "finish_reason": "",
        "content_present": False,
        "tool_calls": "",
        "works_for_pipeline": False,
        "error": "",
        "content_preview": "",
    }
    if not response.ok:
        result["error"] = response.text[:500]
        return result

    data = response.json()
    choice = (data.get("choices") or [{}])[0]
    message = choice.get("message") or {}
    content = message.get("content")
    tool_calls = message.get("tool_calls") or []
    tool_names = [tc.get("function", {}).get("name", "") for tc in tool_calls]

    result["finish_reason"] = str(choice.get("finish_reason", ""))
    result["content_present"] = bool(content)
    result["tool_calls"] = ",".join(name for name in tool_names if name)
    result["content_preview"] = str(content or json.dumps(message, ensure_ascii=False))[:500]
    result["works_for_pipeline"] = bool(content) and result["finish_reason"] == "stop"
    return result


def post_chat(model: str, payload_extra: dict) -> requests.Response:
    endpoint = f"{BASE_URL}/api/chat/completions"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": PROMPT}],
        **payload_extra,
    }
    return requests.post(endpoint, headers=headers, json=payload, timeout=(30, 180))


def main() -> None:
    print("base_url:", BASE_URL)
    rows = []

    for model in MODELS:
        print(f"\n=== {model} ===")

        checks = {
            "plain_chat_no_web": {},
            "features_web_search_true": {"features": {"web_search": True}},
            "tool_ids_web_search": {"tool_ids": ["web_search"]},
        }

        model_rows = {}
        for check_name, payload_extra in checks.items():
            try:
                response = post_chat(model, payload_extra)
                result = classify_response(response)
            except Exception as exc:
                result = {
                    "status_code": "",
                    "finish_reason": "",
                    "content_present": False,
                    "tool_calls": "",
                    "works_for_pipeline": False,
                    "error": str(exc),
                    "content_preview": "",
                }

            row = {"model": model, "check": check_name, **result}
            rows.append(row)
            model_rows[check_name] = row
            print(
                f"{check_name}: status={row['status_code']} "
                f"finish={row['finish_reason']} content={row['content_present']} "
                f"tools={row['tool_calls']} works={row['works_for_pipeline']}"
            )

        web_ok = model_rows.get("tool_ids_web_search", {}).get("works_for_pipeline", False)
        no_web_ok = model_rows.get("plain_chat_no_web", {}).get("works_for_pipeline", False)
        print(f"recommended: NO_WEB={'yes' if no_web_ok else 'no'} WEB_SEARCH={'yes' if web_ok else 'no'}")

    with OUT_PATH.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "model",
                "check",
                "status_code",
                "finish_reason",
                "content_present",
                "tool_calls",
                "works_for_pipeline",
                "error",
                "content_preview",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nSaved: {OUT_PATH}")


if __name__ == "__main__":
    main()
