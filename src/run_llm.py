import argparse
import json
import os
import re
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
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


def create_client(cfg: dict) -> OpenAI:
    api_base_url = cfg.get("api_base_url")
    api_key_env = cfg.get("api_key_env")
    api_key = None
    if api_key_env:
        api_key = os.getenv(api_key_env)
        if not api_key:
            raise SystemExit(f"Set {api_key_env} in your environment first.")
    if api_base_url or api_key:
        return OpenAI(base_url=api_base_url or None, api_key=api_key)
    return OpenAI()


def _response_text(response) -> str:
    if getattr(response, "output_text", None):
        return response.output_text
    if getattr(response, "choices", None):
        try:
            return response.choices[0].message.content or ""
        except Exception:
            pass
    texts = []
    for out in getattr(response, "output", []) or []:
        for content in getattr(out, "content", []) or []:
            text = getattr(content, "text", None)
            if text:
                texts.append(text)
    return "\n".join(texts)


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


def _serialize_response(response) -> str:
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
    queries_path = Path("queries.csv")
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

    client = create_client(cfg)
    top_k = int(cfg.get("top_k_return", 10))
    modes = [m.strip().upper() for m in cfg.get("modes", ["NO_WEB", "WEB_SEARCH"])]
    if _is_openwebui(cfg) and "WEB_SEARCH" in modes:
        print("INFO: OpenWebUI detected. Removing WEB_SEARCH mode (tools not supported).")
        modes = [m for m in modes if m != "WEB_SEARCH"]
    if not modes:
        modes = ["NO_WEB"]

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

    os.makedirs("logs", exist_ok=True)
    rows = []
    warned_web_fallback = False
    force_chat = False

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
                    "Only include GESIS-hosted landing pages or DOIs. Do not invent links."
                )

            user_msg = (
                f"Query: {query_text}\n"
                f"Return up to {top_k} items. "
                "Respond ONLY with JSON matching the schema."
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

            max_retries = 2
            last_response = None
            parsed = None
            response_mode = "responses"
            for attempt in range(max_retries + 1):
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
                    )
                    warned_web_fallback = True

                if response_mode == "responses" and getattr(last_response, "output_parsed", None):
                    parsed = last_response.output_parsed
                    break

                text = _response_text(last_response)
                try:
                    parsed = _extract_json(text)
                    break
                except Exception:
                    if attempt < max_retries:
                        messages.append(
                            {
                                "role": "user",
                                "content": "Your last response was invalid. Return ONLY valid JSON matching the schema.",
                            }
                        )
                        continue

            if parsed is None:
                parsed = {"items": []}

            raw_path = Path("logs") / f"query_{query_id}_{mode}.json"
            try:
                raw_path.write_text(_serialize_response(last_response), encoding="utf-8")
            except Exception:
                raw_path.write_text(str(last_response), encoding="utf-8")

            items = parsed.get("items", []) if isinstance(parsed, dict) else []
            if not isinstance(items, list):
                items = []

            if retrieval_for_candidates and candidate_text:
                items = _post_filter_candidates(items, candidate_links, candidate_titles)

            for rank, item in enumerate(items[:top_k], start=1):
                rows.append(
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

    out = pd.DataFrame(rows)
    out.to_csv("llm_results.csv", index=False)
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, help="Path to config.yaml")
    args = parser.parse_args()
    run_llm(args.config)


if __name__ == "__main__":
    main()
