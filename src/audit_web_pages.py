import argparse
import re
from html import unescape
from pathlib import Path

import pandas as pd
import requests
import yaml

from .config_paths import apply_variant_override, resolve_output_dir
from .match_and_eval import _normalize_label

OUTPUT_CSV_SEP = ";"
RE_TAG = re.compile(r"<[^>]+>")
RE_TITLE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
RE_H1 = re.compile(r"<h1[^>]*>(.*?)</h1>", re.IGNORECASE | re.DOTALL)
RE_GESIS_ID = re.compile(r"\b(?:ZA\d+|SDN-10\.7802-\d+)\b", re.IGNORECASE)
RE_DBK_NO = re.compile(r"[?&]no=(\d+)", re.IGNORECASE)
RE_RESEARCH_DATA = re.compile(r"/research_data/(ZA\d+|SDN-10\.7802-\d+)", re.IGNORECASE)


def load_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def clean_html_text(value: str) -> str:
    text = RE_TAG.sub(" ", value or "")
    text = unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def extract_first(pattern: re.Pattern, html: str) -> str:
    match = pattern.search(html or "")
    if not match:
        return ""
    return clean_html_text(match.group(1))


def normalize_title_for_compare(value: str) -> str:
    text = _normalize_label(value)
    text = text.replace("&", " and ")
    text = re.sub(r"[-–—:;,.()\\[\\]/]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def title_similarity(left: str, right: str) -> float:
    left_norm = normalize_title_for_compare(left)
    right_norm = normalize_title_for_compare(right)
    if not left_norm or not right_norm:
        return 0.0
    left_tokens = set(left_norm.split())
    right_tokens = set(right_norm.split())
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


def extract_gensis_ids(text: str) -> list[str]:
    ids = []
    for match in RE_GESIS_ID.finditer(text or ""):
        value = match.group(0).upper()
        if value not in ids:
            ids.append(value)
    return ids


def id_from_url(url: str) -> str:
    research_data = RE_RESEARCH_DATA.search(url or "")
    if research_data:
        return research_data.group(1).upper()
    dbk = RE_DBK_NO.search(url or "")
    if dbk:
        return f"ZA{int(dbk.group(1)):04d}"
    return ""


def fetch_page(url: str, timeout: int) -> dict:
    if not str(url or "").strip():
        return {
            "fetch_status": "empty_url",
            "http_status": "",
            "final_url": "",
            "page_title": "",
            "page_h1": "",
            "page_text_sample": "",
            "fetch_error": "",
        }

    headers = {
        "User-Agent": "GESIS dataset findability audit/0.1 (+https://github.com/momenifi/Findability-of-Gesis-dataset-by-LLMs)"
    }
    try:
        response = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
        html = response.text or ""
        page_title = extract_first(RE_TITLE, html)
        page_h1 = extract_first(RE_H1, html)
        page_text = clean_html_text(html)[:2000]
        return {
            "fetch_status": "ok",
            "http_status": response.status_code,
            "final_url": response.url,
            "page_title": page_title,
            "page_h1": page_h1,
            "page_text_sample": page_text,
            "fetch_error": "",
        }
    except Exception as exc:
        return {
            "fetch_status": "error",
            "http_status": "",
            "final_url": "",
            "page_title": "",
            "page_h1": "",
            "page_text_sample": "",
            "fetch_error": str(exc),
        }


def classify_row(row: pd.Series, page: dict) -> dict:
    source_id = str(row.get("source_dataset_id", "") or "").strip().upper()
    matched_id = str(row.get("matched_dataset_id", "") or "").strip().upper()
    returned_title = str(row.get("returned_title", "") or "")
    source_title = str(row.get("source_title", "") or "")
    page_title = str(page.get("page_title", "") or "")
    page_h1 = str(page.get("page_h1", "") or "")
    final_url = str(page.get("final_url", "") or "")
    page_text = str(page.get("page_text_sample", "") or "")

    final_url_id = id_from_url(final_url)
    page_ids = extract_gensis_ids(" ".join([final_url, page_title, page_h1, page_text]))
    resolved_id = final_url_id or (page_ids[0] if page_ids else "")

    best_page_title = page_h1 or page_title
    source_page_title_similarity = title_similarity(source_title, best_page_title)
    returned_page_title_similarity = title_similarity(returned_title, best_page_title)
    source_returned_title_similarity = title_similarity(source_title, returned_title)

    if source_id and resolved_id == source_id:
        audit_class = "resolved_to_source"
    elif source_id and matched_id == source_id:
        audit_class = "matched_source_without_page_id"
    elif source_id and resolved_id and resolved_id != source_id and source_page_title_similarity >= 0.75:
        audit_class = "different_dataset_similar_title"
    elif source_id and matched_id and matched_id != source_id and source_returned_title_similarity >= 0.75:
        audit_class = "different_dataset_similar_returned_title"
    elif resolved_id:
        audit_class = "resolved_to_different_dataset"
    elif page.get("fetch_status") == "ok":
        audit_class = "resolved_page_no_dataset_id"
    else:
        audit_class = "not_checked"

    return {
        "resolved_dataset_id_from_page": resolved_id,
        "page_dataset_ids": ",".join(page_ids),
        "page_title_best": best_page_title,
        "source_page_title_similarity": round(source_page_title_similarity, 3),
        "returned_page_title_similarity": round(returned_page_title_similarity, 3),
        "source_returned_title_similarity": round(source_returned_title_similarity, 3),
        "web_audit_class": audit_class,
    }


def audit_web_pages(config_path: str, variant: str | None, query_ids: list[int] | None, timeout: int) -> None:
    cfg = apply_variant_override(load_config(config_path), variant)
    output_dir = resolve_output_dir(cfg)
    per_query_path = output_dir / "per_query_results.csv"
    queries_path = output_dir / "queries.csv"

    if not per_query_path.exists():
        raise FileNotFoundError(f"{per_query_path} not found. Run match_and_eval first.")

    results = pd.read_csv(per_query_path, sep=None, engine="python")
    if queries_path.exists():
        queries = pd.read_csv(queries_path, sep=None, engine="python")
        source_cols = ["query_id", "source_title", "source_doi", "source_portal_url"]
        source_cols = [col for col in source_cols if col in queries.columns and col not in results.columns]
        if source_cols:
            results = results.merge(queries[["query_id"] + source_cols].drop_duplicates("query_id"), on="query_id", how="left")

    if query_ids:
        results = results[results["query_id"].isin(query_ids)].copy()

    rows = []
    cache = {}
    for _, row in results.iterrows():
        url = str(row.get("returned_url_or_doi", "") or "").strip()
        if url not in cache:
            cache[url] = fetch_page(url, timeout)
        page = cache[url]
        classification = classify_row(row, page)
        rows.append({**row.to_dict(), **page, **classification})

    audit_df = pd.DataFrame(rows)
    output_path = output_dir / "web_page_audit.csv"
    audit_df.to_csv(output_path, index=False, sep=OUTPUT_CSV_SEP)

    summary = (
        audit_df.groupby(["query_variant", "mode", "model", "web_audit_class"], dropna=False)
        .size()
        .reset_index(name="item_rows")
    )
    summary_path = output_dir / "web_page_audit_summary.csv"
    summary.to_csv(summary_path, index=False, sep=OUTPUT_CSV_SEP)

    print(f"Wrote {output_path}")
    print(f"Wrote {summary_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch returned dataset links and compare resolved page content.")
    parser.add_argument("--config", required=True)
    parser.add_argument("-V", "--variant", default=None)
    parser.add_argument("--query-ids", nargs="*", type=int, default=None)
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    audit_web_pages(args.config, args.variant, args.query_ids, args.timeout)


if __name__ == "__main__":
    main()
