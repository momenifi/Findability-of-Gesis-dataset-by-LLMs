import json
import os

import requests


BASE_URL = os.getenv("OPENWEBUI_BASE_URL", "https://ai-openwebui.gesis.org").rstrip("/")
API_KEY = os.getenv("OPENWEBUI_API_KEY")
MODEL = os.getenv("OPENWEBUI_TEST_MODEL", "gpt-5.1")

if not API_KEY:
    raise SystemExit("Set OPENWEBUI_API_KEY in your environment first.")


def summarize_response(label: str, response: requests.Response) -> None:
    print(f"\n=== {label} ===")
    print("status:", response.status_code)
    if not response.ok:
        print(response.text[:2000])
        return

    data = response.json()
    choice = (data.get("choices") or [{}])[0]
    message = choice.get("message") or {}
    content = message.get("content")
    tool_calls = message.get("tool_calls") or []

    print("finish_reason:", choice.get("finish_reason"))
    print("content_present:", bool(content))
    print("tool_calls:", [tc.get("function", {}).get("name") for tc in tool_calls])
    if content:
        print("content_preview:", str(content)[:1000])
    else:
        print("message_preview:", json.dumps(message, indent=2, ensure_ascii=False)[:1500])


def post_chat(label: str, extra_payload: dict) -> None:
    endpoint = f"{BASE_URL}/api/chat/completions"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": MODEL,
        "messages": [
            {
                "role": "user",
                "content": (
                    "Use web search if available. Find the GESIS dataset titled "
                    "'Federal Parliament Election 1972 (Panel: 2nd Wave, October 1971 - January 1972)'. "
                    "Return ONLY JSON: {\"items\":[{\"title\":\"...\",\"url_or_doi\":\"...\"}]}"
                ),
            }
        ],
        **extra_payload,
    }
    response = requests.post(endpoint, headers=headers, json=payload, timeout=(30, 180))
    summarize_response(label, response)


def main() -> None:
    print("base_url:", BASE_URL)
    print("model:", MODEL)
    post_chat("plain_chat_no_web", {})
    post_chat("features_web_search_true", {"features": {"web_search": True}})
    post_chat("tool_ids_web_search", {"tool_ids": ["web_search"]})


if __name__ == "__main__":
    main()
