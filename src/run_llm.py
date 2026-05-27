import argparse
import json
import os
import re
import time
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd
import requests
import yaml
from openai import APIStatusError, OpenAI

from .load_metadata import load_metadata

RE_DOI = re.compile(r"10\.\d{4,9}/\S+", re.IGNORECASE)


class BM25:
    def __init__(self, k1: float = 1.5, b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b
        self.doc_freqs = []
        self.idf = {}
        self.doc_len = []
        self.avgdl = 0.0
        self.vocab = set()

    @staticmethod
    def tokenize(text: str) -> List[str]:
        return re.findall(r"[a-zA-Z0-9]+", (text or "").lower())

    def fit(self, corpus: List[str]) -> None:
        self.doc_freqs = []
        self.doc_len = []
        df = {}
        for doc in corpus:
            tokens = self.tokenize(doc)
            self.doc_len.append(len(tokens))
            freqs = {}
            for t in tokens:
                freqs[t] = freqs.get(t, 0) + 1
            self.doc_freqs.append(freqs)
            for t in freqs.keys():
                df[t] = df.get(t, 0) + 1
        self.avgdl = float(np.mean(self.doc_len)) if self.doc_len else 0.0
        n_docs = len(corpus)
        self.idf = {}
        for t, freq in df.items():
            self.idf[t] = np.log(1 + (n_docs - freq + 0.5) / (freq + 0.5))
        self.vocab = set(self.idf.keys())

    def get_scores(self, query: str) -> np.ndarray:
        q_tokens = self.tokenize(query)
        scores = np.zeros(len(self.doc_freqs), dtype=float)
        for i, freqs in enumerate(self.doc_freqs):
            dl = self.doc_len[i] if i < len(self.doc_len) else 0
            for t in q_tokens:
                if t not in freqs:
                    continue
                idf = self.idf.get(t, 0.0)
                tf = freqs[t]
                denom = tf + self.k1 * (1 - self.b + self.b * dl / (self.avgdl or 1.0))
                scores[i] += idf * (tf * (self.k1 + 1) / (denom or 1.0))
        return scores

    def top_k(self, query: str, k: int) -> List[int]:
        scores = self.get_scores(query)
        if len(scores) == 0:
            return []
        idx = np.argsort(-scores)
        return idx[:k].tolist()


def load_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_api_key(cfg: dict) -> str | None:
    api_key_env = cfg.get("api_key_env")
    if not api_key_env:
        return None
    api_key = os.getenv(api_key_env)
    if not api_key:
        raise SystemExit(f"Set {api_key_env} in your environment first.")
    return api_key


def create_client(cfg: dict) -> OpenAI:
    api_base_url = cfg.get("api_base_url")
    api_key = get_api_key(cfg)
    if api_base_url or api_key:
        return OpenAI(base_url=api_base_url or None, api_key=api_key)
    return OpenAI()


def _content_to_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        texts = []
        for part in content:
            if isinstance(part, dict):
                text = part.get("text") or part.get("content")
                if isinstance(text, str) and text:
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
            pass
    texts = []
    for out in getattr(response, "output", []) or []:
        for content in getattr(out, "content", []) or []:
            text = getattr(content, "text", None)
            if text:
                texts.append(text)
    return "\n".join(texts)


def _tool_call_names(response) -> List[str]:
    if not isinstance(response, dict):
        return []
    choices = response.get("choices") or []
    if not choices:
        return []
    message = choices[0].get("message") or {}
    tool_calls = message.get("tool_calls") or []
    names = []
    for tool_call in tool_calls:
        function = tool_call.get("function") or {}
        name = function.get("name")
        if name:
            names.append(str(name))
    return names


def _parse_json(text: str) -> dict:
    return json.loads(text)


def _extract_json(text: str) -> dict:
    try:
        return _parse_json(text)
    except Exception:
        pass
    if not text:
        raise ValueError("Empty response text")
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("No JSON object found")
    return _parse_json(text[start : end + 1])


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
            or item.get("gesis_doi_or_landing_page")
            or ""
        ).strip()
        justification = str(item.get("justification") or item.get("reason") or item.get("explanation") or "").strip()

        if title or url_or_doi:
            items.append(
                {
                    "title": title,
                    "url_or_doi": url_or_doi,
                    "justification": justification,
                }
            )
    return items


def _serialize_response(response) -> str:
    if isinstance(response, (dict, list)):
        return json.dumps(response, indent=2, ensure_ascii=False)
    if hasattr(response, "model_dump_json"):
        return response.model_dump_json(indent=2)
    if hasattr(response, "model_dump"):
        return json.dumps(response.model_dump(), indent=2)
    try:
        return json.dumps(response, default=str, indent=2)
    except Exception:
        return str(response)


def _create_response(client: OpenAI, kwargs: dict):
    try:
        return client.responses.create(**kwargs)
    except TypeError as e:
        msg = str(e)
        if "response_format" in msg:
            kwargs = dict(kwargs)
            kwargs.pop("response_format", None)
            return client.responses.create(**kwargs)
        if "tools" in msg:
            kwargs = dict(kwargs)
            kwargs.pop("tools", None)
            return client.responses.create(**kwargs)
        raise


def _create_response_or_chat(client: OpenAI, response_kwargs: dict, chat_kwargs: dict):
    try:
        return "responses", _create_response(client, response_kwargs)
    except APIStatusError as e:
        status = getattr(e, "status_code", None)
        msg = str(e)
        if status in (404, 405) or "Method Not Allowed" in msg or "Not Found" in msg:
            return "chat", client.chat.completions.create(**chat_kwargs)
        raise


def _is_openwebui(cfg: dict) -> bool:
    base_url = str(cfg.get("api_base_url") or "").lower()
    api_key_env = str(cfg.get("api_key_env") or "").lower()
    return "openwebui" in base_url or api_key_env == "openwebui_api_key"


def _openwebui_chat_endpoint(cfg: dict) -> str:
    base_url = str(cfg.get("api_base_url") or "").rstrip("/")
    if not base_url:
        raise ValueError("api_base_url is required for OpenWebUI requests.")
    if base_url.endswith("/api"):
        return f"{base_url}/chat/completions"
    return f"{base_url}/api/chat/completions"


def _call_openwebui_chat(cfg: dict, model: str, messages: List[dict], enable_web_search: bool) -> dict:
    api_key = get_api_key(cfg)
    endpoint = _openwebui_chat_endpoint(cfg)
    connect_timeout = float(cfg.get("request_timeout_connect_seconds", 30))
    read_timeout = float(cfg.get("request_timeout_read_seconds", 180))
    payload = {
        "model": model,
        "messages": messages,
    }
    if enable_web_search:
        web_search_mode = str(cfg.get("openwebui_web_search_mode", "tool_ids")).strip().lower()
        if web_search_mode == "features":
            payload["features"] = {"web_search": True}
        elif web_search_mode == "tool_ids":
            payload["tool_ids"] = ["web_search"]
        else:
            raise ValueError(f"Unsupported openwebui_web_search_mode: {web_search_mode}")
    if bool(cfg.get("openwebui_include_sampling_params", False)) and "temperature" in cfg:
        payload["temperature"] = float(cfg.get("temperature", 0))
    if bool(cfg.get("openwebui_include_sampling_params", False)) and "top_p" in cfg:
        payload["top_p"] = float(cfg.get("top_p", 1))
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    def post_payload(body: dict):
        return requests.post(
            endpoint,
            headers=headers,
            json=body,
            timeout=(connect_timeout, read_timeout),
        )

    try:
        response = post_payload(payload)
        if (
            response.status_code == 400
            and enable_web_search
            and "NoneType" in response.text
            and "startswith" in response.text
        ):
            fallback_payload = dict(payload)
            fallback_payload.pop("features", None)
            fallback_payload["tool_ids"] = ["web_search"]
            response = post_payload(fallback_payload)
    except (requests.Timeout, TimeoutError) as e:
        raise RuntimeError(
            "OpenWebUI chat request timed out. "
            f"connect_timeout={connect_timeout}s read_timeout={read_timeout}s "
            "This usually means web search or the model response is taking too long on the server."
        ) from e
    except requests.RequestException as e:
        raise RuntimeError(f"OpenWebUI chat request failed before a response was received: {e}") from e
    try:
        response.raise_for_status()
    except requests.HTTPError as e:
        snippet = response.text[:1500]
        raise RuntimeError(f"OpenWebUI chat request failed with {response.status_code}: {snippet}") from e
    try:
        return response.json()
    except ValueError as e:
        raise RuntimeError(f"OpenWebUI returned non-JSON content: {response.text[:1500]}") from e


def _build_candidate_text(df: pd.DataFrame, idxs: List[int]) -> str:
    lines = []
    for rank, i in enumerate(idxs, start=1):
        row = df.iloc[i]
        title = str(row.get("title", "")).strip()
        link = str(row.get("link", "")).strip()
        doi = str(row.get("doi", "")).strip()
        link_or_doi = link or (f"https://doi.org/{doi}" if doi else "")
        if not title and not link_or_doi:
            continue
        lines.append(f"{rank}. {title} | {link_or_doi}")
    return "\n".join(lines)


def _post_filter_candidates(items: List[dict], candidate_links: set, candidate_titles: set) -> List[dict]:
    filtered = []
    for it in items:
        title = str(it.get("title", "")).strip().lower()
        link = str(it.get("url_or_doi", "")).strip().lower()
        if link and link in candidate_links:
            filtered.append(it)
            continue
        if title and title in candidate_titles:
            filtered.append(it)
    return filtered


def run_llm(config_path: str) -> pd.DataFrame:
    cfg = load_config(config_path)
    output_dir = Path(cfg.get("output_dir", "."))
    output_dir.mkdir(parents=True, exist_ok=True)
    queries_path = output_dir / "queries.csv"
    if not queries_path.exists():
        raise FileNotFoundError("queries.csv not found. Run generate_queries first.")

    queries = pd.read_csv(queries_path)
    df = load_metadata(cfg["input_path"], cfg["input_format"])

    retrieval_for_candidates = bool(cfg.get("retrieval_for_candidates", False))
    retrieval_candidates_k = int(cfg.get("retrieval_candidates_k", 30))

    bm25 = None
    if retrieval_for_candidates:
        corpus = []
        for _, row in df.iterrows():
            text = " ".join(
                [
                    str(row.get("title", "")),
                    str(row.get("abstract", "")),
                    str(row.get("topic", "")),
                    str(row.get("categories", "")),
                    str(row.get("content_description", "")),
                    str(row.get("topics_stw", "")),
                    str(row.get("topics_thesoz", "")),
                    str(row.get("universe", "")),
                ]
            )
            corpus.append(text)
        bm25 = BM25()
        bm25.fit(corpus)

    use_openwebui_native = _is_openwebui(cfg)
    client = None if use_openwebui_native else create_client(cfg)
    top_k = int(cfg.get("top_k_return", 10))
    modes = [m.strip().upper() for m in cfg.get("modes", ["NO_WEB", "WEB_SEARCH"])]
    if not modes:
        modes = ["NO_WEB"]
    total_requests = len(queries) * len(modes)

    if use_openwebui_native and "WEB_SEARCH" in modes:
        print(
            "INFO: Using OpenWebUI native /api/chat/completions for WEB_SEARCH. "
            "Ensure web search is enabled globally and on the selected OpenWebUI model."
        , flush=True)

    response_schema = {
        "name": "gesis_results",
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "title": {"type": "string"},
                            "url_or_doi": {"type": "string"},
                            "justification": {"type": "string"},
                        },
                        "required": ["title", "url_or_doi", "justification"],
                    },
                }
            },
            "required": ["items"],
        },
        "strict": True,
    }

    logs_dir = output_dir / "logs"
    os.makedirs(logs_dir, exist_ok=True)
    results_path = output_dir / "llm_results.csv"
    if results_path.exists():
        results_path.unlink()
    rows = []
    warned_web_fallback = False
    force_chat = False
    completed_requests = 0

    for _, q in queries.iterrows():
        query_id = q["query_id"]
        query_text = str(q["query_text"]) if not pd.isna(q["query_text"]) else ""
        query_variant = q["query_variant"]

        for mode in modes:
            mode = mode.strip().upper()
            model = cfg.get("model_no_web") if mode == "NO_WEB" else cfg.get("model_web")

            candidate_text = ""
            candidate_links = set()
            candidate_titles = set()
            if retrieval_for_candidates and bm25 is not None:
                idxs = bm25.top_k(query_text, retrieval_candidates_k)
                candidate_text = _build_candidate_text(df, idxs)
                for i in idxs:
                    row = df.iloc[i]
                    link = str(row.get("link", "")).strip().lower()
                    title = str(row.get("title", "")).strip().lower()
                    if link:
                        candidate_links.add(link)
                    if title:
                        candidate_titles.add(title)

            if mode == "NO_WEB":
                system_msg = (
                    "Do not browse the web. Use only your internal knowledge. "
                    "Only include datasets hosted by GESIS. Do not invent links; if unsure, omit the item."
                )
            else:
                system_msg = (
                    "Use web search to find relevant datasets hosted by GESIS. "
                    "Only include GESIS-hosted landing pages or DOIs. Do not invent links. "
                    "Do not call time, date, timestamp, or clock tools."
                )

            user_msg = (
                f"Query: {query_text}\n"
                f"Return up to {top_k} items. "
                "Respond ONLY as JSON in this exact shape: "
                '{"items":[{"title":"...","url_or_doi":"...","justification":"..."}]}. '
                "Put any DOI, GESIS URL, landing page, or link in url_or_doi."
            )

            if retrieval_for_candidates and candidate_text:
                user_msg += (
                    "\nYou MUST choose only from the candidate list below and copy the title and URL/DOI exactly."
                    f"\nCandidate list:\n{candidate_text}"
                )

            messages = [
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg},
            ]

            max_retries = int(cfg.get("request_max_retries", 2))
            retry_backoff_seconds = float(cfg.get("request_retry_backoff_seconds", 5))
            last_response = None
            parsed = None
            response_mode = "responses"
            request_failed = False
            for attempt in range(max_retries + 1):
                print(
                    f"START [{completed_requests + 1}/{total_requests}] "
                    f"query_id={query_id} variant={query_variant} mode={mode} attempt={attempt + 1}",
                    flush=True,
                )
                try:
                    if use_openwebui_native:
                        response_mode = "openwebui_chat"
                        last_response = _call_openwebui_chat(
                            cfg=cfg,
                            model=model,
                            messages=messages,
                            enable_web_search=(mode == "WEB_SEARCH"),
                        )
                    else:
                        kwargs = {
                            "model": model,
                            "input": messages,
                            "response_format": {"type": "json_schema", "json_schema": response_schema},
                        }
                        if mode == "WEB_SEARCH":
                            kwargs["tools"] = [{"type": "web_search"}]

                        chat_kwargs = {
                            "model": model,
                            "messages": messages,
                        }

                        if force_chat:
                            response_mode = "chat"
                            last_response = client.chat.completions.create(**chat_kwargs)
                        else:
                            response_mode, last_response = _create_response_or_chat(client, kwargs, chat_kwargs)
                            if response_mode == "chat":
                                force_chat = True

                        if response_mode == "chat" and mode == "WEB_SEARCH" and not warned_web_fallback:
                            print(
                                "WARNING: WEB_SEARCH mode is not supported by this API endpoint; "
                                "falling back to chat completions without tools."
                            , flush=True)
                            warned_web_fallback = True

                        if response_mode == "responses" and getattr(last_response, "output_parsed", None):
                            parsed = last_response.output_parsed
                            break
                except Exception as e:
                    last_response = {
                        "error": str(e),
                        "query_id": int(query_id),
                        "query_variant": query_variant,
                        "mode": mode,
                        "attempt": attempt + 1,
                    }
                    if attempt < max_retries:
                        wait_seconds = retry_backoff_seconds * (attempt + 1)
                        print(
                            f"RETRY query_id={query_id} variant={query_variant} mode={mode} "
                            f"after error: {e} (sleep {wait_seconds:.1f}s)",
                            flush=True,
                        )
                        time.sleep(wait_seconds)
                        continue
                    request_failed = True
                    print(
                        f"FAILED query_id={query_id} variant={query_variant} mode={mode}: {e}",
                        flush=True,
                    )
                    break

                text = _response_text(last_response)
                try:
                    parsed = _extract_json(text)
                    break
                except Exception:
                    if attempt < max_retries:
                        tool_call_names = _tool_call_names(last_response)
                        if tool_call_names:
                            invalid_response_note = (
                                "Your last response only contained tool calls "
                                f"({', '.join(tool_call_names)}) and no final JSON content. "
                                "Do not call get_current_timestamp or any time/date tool. "
                                "If web search is available, use only web_search and then return final JSON. "
                            )
                        else:
                            invalid_response_note = "Your last response was invalid. "
                        messages.append(
                            {
                                "role": "user",
                                "content": (
                                    invalid_response_note
                                    + "Return ONLY valid JSON in this exact shape: "
                                    '{"items":[{"title":"...","url_or_doi":"...","justification":"..."}]}.'
                                ),
                            }
                        )
                        continue

            if request_failed and parsed is None:
                parsed = {"items": []}

            if parsed is None:
                parsed = {"items": []}

            raw_path = logs_dir / f"query_{query_id}_{mode}.json"
            try:
                raw_path.write_text(_serialize_response(last_response), encoding="utf-8")
            except Exception:
                raw_path.write_text(str(last_response), encoding="utf-8")

            items = _extract_items(parsed)

            if retrieval_for_candidates and candidate_text:
                items = _post_filter_candidates(items, candidate_links, candidate_titles)

            batch_rows = []
            for rank, item in enumerate(items[:top_k], start=1):
                record = (
                    {
                        "query_id": query_id,
                        "query_variant": query_variant,
                        "mode": mode,
                        "rank": rank,
                        "returned_title": str(item.get("title", "")),
                        "returned_url_or_doi": str(item.get("url_or_doi", "")),
                        "justification": str(item.get("justification", "")),
                        "raw_response_path": str(raw_path),
                    }
                )
                rows.append(record)
                batch_rows.append(record)

            if batch_rows:
                pd.DataFrame(batch_rows).to_csv(
                    results_path,
                    mode="a",
                    header=not results_path.exists(),
                    index=False,
                )

            completed_requests += 1
            print(
                f"[{completed_requests}/{total_requests}] "
                f"query_id={query_id} variant={query_variant} mode={mode} items={len(items[:top_k])}"
                ,
                flush=True,
            )

    out = pd.DataFrame(rows)
    if not results_path.exists():
        out.to_csv(results_path, index=False)
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, help="Path to config.yaml")
    args = parser.parse_args()
    run_llm(args.config)


if __name__ == "__main__":
    main()
