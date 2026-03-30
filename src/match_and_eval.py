import argparse
import math
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

import numpy as np
import pandas as pd
import yaml
from rapidfuzz import fuzz, process
from sklearn.feature_extraction.text import TfidfVectorizer

from .load_metadata import load_metadata

RE_DOI = re.compile(r"10\.\d{4,9}/\S+", re.IGNORECASE)


def load_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _normalize_doi(raw: str) -> str:
    doi = (raw or "").strip()
    if not doi:
        return ""
    doi = re.sub(r"^doi:\s*", "", doi, flags=re.IGNORECASE)
    doi = doi.replace("https://doi.org/", "").replace("http://doi.org/", "")
    doi = doi.replace("https://dx.doi.org/", "").replace("http://dx.doi.org/", "")
    doi = doi.split("?")[0].split("#")[0]
    doi = doi.strip().strip("<>")
    return doi


def _extract_doi(text: str) -> str:
    if not text:
        return ""
    t = text.strip()
    if "doi.org/" in t:
        part = t.split("doi.org/", 1)[1]
        return _normalize_doi(part)
    match = RE_DOI.search(t)
    if match:
        return _normalize_doi(match.group(0))
    return ""


def _normalize_url(url: str) -> str:
    u = (url or "").strip().lower()
    if u.endswith("/"):
        u = u[:-1]
    return u


def build_qrels(df: pd.DataFrame, queries: pd.DataFrame, fields: List[str], top_m: int) -> Dict[int, List[str]]:
    texts = []
    for _, row in df.iterrows():
        parts = []
        for f in fields:
            parts.append(str(row.get(f, "")))
        texts.append(_normalize_whitespace(" ".join(parts)))

    vectorizer = TfidfVectorizer(stop_words="english")
    doc_matrix = vectorizer.fit_transform(texts)

    qrels_map: Dict[int, List[str]] = {}
    for _, q in queries.iterrows():
        query_id = int(q["query_id"])
        qtext = _normalize_whitespace(str(q["query_text"]))
        q_vec = vectorizer.transform([qtext])
        sims = (doc_matrix @ q_vec.T).toarray().ravel()
        if np.all(sims == 0):
            continue
        top_idx = np.argsort(-sims)[:top_m]
        relevant_ids = [str(df.iloc[i]["id"]) for i in top_idx]
        if relevant_ids:
            qrels_map[query_id] = relevant_ids
    return qrels_map


def match_items(
    results: pd.DataFrame, df: pd.DataFrame
) -> Tuple[pd.DataFrame, Dict[str, str], Dict[str, str]]:
    doi_to_id = {}
    portal_to_id = {}

    for _, row in df.iterrows():
        did = str(row.get("id", ""))
        doi = _normalize_doi(str(row.get("doi", "")))
        portal = _normalize_url(str(row.get("portal_url", "")))
        if doi:
            doi_to_id[doi] = did
        if portal:
            portal_to_id[portal] = did

    titles = df["title"].fillna("").astype(str).tolist()
    ids = df["id"].fillna("").astype(str).tolist()

    matched_ids = []
    confidences = []
    link_valids = []

    for _, row in results.iterrows():
        link_or_doi = str(row.get("returned_url_or_doi", ""))
        title = str(row.get("returned_title", ""))

        matched_id = ""
        confidence = 0.0

        doi = _extract_doi(link_or_doi)
        if doi and doi in doi_to_id:
            matched_id = doi_to_id[doi]
            confidence = 1.0
        else:
            portal = _normalize_url(link_or_doi)
            if portal in portal_to_id:
                matched_id = portal_to_id[portal]
                confidence = 1.0
            else:
                if title:
                    best = process.extractOne(title, titles, scorer=fuzz.token_set_ratio)
                    if best:
                        best_title, score, idx = best
                        if score >= 70:
                            matched_id = ids[idx]
                            confidence = float(score) / 100.0

        link_valid = False
        if doi:
            link_valid = doi in doi_to_id
        else:
            portal = _normalize_url(link_or_doi)
            link_valid = portal in portal_to_id

        matched_ids.append(matched_id)
        confidences.append(confidence)
        link_valids.append(link_valid)

    results = results.copy()
    results["matched_dataset_id"] = matched_ids
    results["match_confidence"] = confidences
    results["link_valid"] = link_valids
    return results, doi_to_id, portal_to_id


def compute_metrics(
    results: pd.DataFrame, qrels_map: Dict[int, List[str]], top_k: int
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    per_query_rows = []
    metrics_rows = []

    for (query_id, variant, mode), group in results.groupby(
        ["query_id", "query_variant", "mode"], sort=False
    ):
        query_id = int(query_id)
        if query_id not in qrels_map:
            continue
        relevant_ids = set(qrels_map[query_id])
        group = group.sort_values("rank")

        matched_ids = group["matched_dataset_id"].tolist()
        link_valids = group["link_valid"].tolist()

        rels = []
        for i in range(top_k):
            if i < len(matched_ids) and matched_ids[i] in relevant_ids:
                rels.append(1)
            else:
                rels.append(0)

        relevant_retrieved = sum(rels)
        precision = relevant_retrieved / float(top_k)
        recall = relevant_retrieved / float(len(relevant_ids) or 1)

        mrr = 0.0
        for idx, mid in enumerate(matched_ids[:top_k], start=1):
            if mid in relevant_ids:
                mrr = 1.0 / idx
                break

        dcg = 0.0
        for i, rel in enumerate(rels, start=1):
            if rel:
                dcg += 1.0 / math.log2(i + 1)

        ideal_rels = [1] * min(len(relevant_ids), top_k)
        idcg = 0.0
        for i, rel in enumerate(ideal_rels, start=1):
            if rel:
                idcg += 1.0 / math.log2(i + 1)
        ndcg = dcg / idcg if idcg > 0 else 0.0

        total_returned = len(matched_ids)
        link_valid_rate = (sum(1 for v in link_valids if v) / total_returned) if total_returned else 0.0
        off_repo_rate = (
            sum(1 for mid in matched_ids if not mid) / total_returned
        ) if total_returned else 0.0

        metrics_rows.append(
            {
                "query_id": query_id,
                "query_variant": variant,
                "mode": mode,
                "precision_at_k": precision,
                "recall_at_k": recall,
                "mrr": mrr,
                "ndcg_at_k": ndcg,
                "link_valid_rate": link_valid_rate,
                "off_repo_rate": off_repo_rate,
            }
        )

        for _, row in group.iterrows():
            per_query_rows.append(
                {
                    **row.to_dict(),
                    "is_relevant": int(row["matched_dataset_id"] in relevant_ids),
                }
            )

    per_query = pd.DataFrame(per_query_rows)
    metrics_per_query = pd.DataFrame(metrics_rows)

    if metrics_per_query.empty:
        summary = pd.DataFrame(
            columns=[
                "query_variant",
                "mode",
                "precision_at_k",
                "recall_at_k",
                "mrr",
                "ndcg_at_k",
                "link_valid_rate",
                "off_repo_rate",
            ]
        )
    else:
        summary = (
            metrics_per_query.groupby(["query_variant", "mode"], sort=False)
            .mean(numeric_only=True)
            .reset_index()
        )

    return per_query, summary


def match_and_eval(config_path: str) -> None:
    cfg = load_config(config_path)

    results_path = Path("llm_results.csv")
    if not results_path.exists():
        raise FileNotFoundError("llm_results.csv not found. Run run_llm first.")

    results = pd.read_csv(results_path)
    queries = pd.read_csv("queries.csv")
    df = load_metadata(cfg["input_path"], cfg["input_format"])

    qrels_fields = cfg.get(
        "silver_qrels_fields",
        [
            "abstract",
            "content_description",
            "categories",
            "topics_stw",
            "topics_thesoz",
            "universe",
        ],
    )
    top_m = int(cfg.get("silver_top_m", 50))

    qrels_map = build_qrels(df, queries, qrels_fields, top_m)
    results, _, _ = match_items(results, df)

    top_k = int(cfg.get("top_k_return", 10))
    per_query, summary = compute_metrics(results, qrels_map, top_k)

    per_query.to_csv("per_query_results.csv", index=False)
    summary.to_csv("metrics_summary.csv", index=False)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, help="Path to config.yaml")
    args = parser.parse_args()
    match_and_eval(args.config)


if __name__ == "__main__":
    main()
