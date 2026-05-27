import os
import requests

BASE_URL = "https://ai-openwebui.gesis.org"
API_KEY = os.getenv("OPENWEBUI_API_KEY")  # set this in your environment
if not API_KEY:
    raise SystemExit("Set OPENWEBUI_API_KEY in your environment first.")

headers = {"Authorization": f"Bearer {API_KEY}"}

# 1) List models
r = requests.get(f"{BASE_URL}/api/models", headers=headers, timeout=30)
r.raise_for_status()
models = r.json()

print("Models:")
for m in models.get("data", []):
    print("-", m.get("id"))

# 2) Use the configured model for a quick chat test
model_id = os.getenv("OPENWEBUI_TEST_MODEL", "gpt-5.1")
print(f"\nTesting model: {model_id}")
payload = {
    "model": model_id,
    "messages": [{"role": "user", "content": "Hello! Reply with one short sentence."}],
}

r = requests.post(f"{BASE_URL}/api/chat/completions", headers=headers, json=payload, timeout=30)
if not r.ok:
    print("\nError response:")
    print(r.text)
r.raise_for_status()
resp = r.json()

print("\nReply:")
print(resp["choices"][0]["message"]["content"])

