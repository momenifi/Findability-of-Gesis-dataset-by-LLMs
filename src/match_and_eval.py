import argparse
import ast
import json
import math
import re
from difflib import SequenceMatcher
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
import yaml
from sklearn.feature_extraction.text import TfidfVectorizer

try:
    from rapidfuzz import fuzz, process
except ImportError:
    fuzz = None
    process = None

from .load_metadata import load_metadata

RE_DOI = re.compile(r"10\.\d{4,9}/\S+", re.IGNORECASE)
RE_ZA_ID = re.compile(r"\bZA\d+\b", re.IGNORECASE)


def load_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _parse_list_value(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [_normalize_whitespace(str(item)) for item in value if _normalize_whitespace(str(item))]

    text = _normalize_whitespace(str(value))
    if not text:
        return []

    parsed = None
    if text.startswith("[") and text.endswith("]"):
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            try:
                parsed = ast.literal_eval(text)
            except (ValueError, SyntaxError):
                parsed = None

    if isinstance(parsed, list):
        return [_normalize_whitespace(str(item)) for item in parsed if _normalize_whitespace(str(item))]

    return [text]


def _normalize_label(value: str) -> str:
    return _normalize_whitespace(value).casefold()


def _label_set(value: object) -> set[str]:
    return {_normalize_label(item) for item in _parse_list_value(value) if _normalize_label(item)}


def _year_range(value: object) -> Tuple[int, int] | None:
    years = []
    for item in _parse_list_value(value):
        years.extend(int(match.group(0)) for match in re.finditer(r"\b\d{4}\b", item))
    if not years:
        return None
    return min(years), max(years)


def _ranges_overlap(left: Tuple[int, int] | None, right: Tuple[int, int] | None) -> bool:
    if left is None or right is None:
        return False
    return left[0] <= right[1] and right[0] <= left[1]


def _best_title_match(title: str, titles: List[str]) -> Tuple[float, int] | None:
    if process is not None and fuzz is not None:
        best = process.extractOne(title, titles, scorer=fuzz.token_set_ratio)
        if not best:
            return None
        _, score, idx = best
        return float(score), int(idx)

    title_norm = _normalize_label(title)
    if not title_norm:
        return None

    best_score = 0.0
    best_idx = -1
    for idx, candidate in enumerate(titles):
        candidate_norm = _normalize_label(candidate)
        if not candidate_norm:
            continue
        score = SequenceMatcher(None, title_norm, candidate_norm).ratio() * 100.0
        if score > best_score:
            best_score = score
            best_idx = idx

    if best_idx < 0:
        return None
    return best_score, best_idx


def _normalize_doi(raw: str) -> str:
    doi = (raw or "").strip()
    if not doi:
        return ""
    if doi.startswith("[") and doi.endswith("]"):
        try:
            parsed = ast.literal_eval(doi)
            if isinstance(parsed, list):
                doi = next((str(item).strip() for item in parsed if str(item).strip()), "")
        except (ValueError, SyntaxError):
            pass
    embedded = RE_DOI.search(doi)
    if embedded:
        doi = embedded.group(0)
    doi = re.sub(r"^doi:\s*", "", doi, flags=re.IGNORECASE)
    doi = doi.replace("https://doi.org/", "").replace("http://doi.org/", "")
    doi = doi.replace("https://dx.doi.org/", "").replace("http://dx.doi.org/", "")
    doi = doi.split("?")[0].split("#")[0]
    doi = doi.strip().strip("<>")
    return doi


def _extract_dataset_id(text: str) -> str:
    match = RE_ZA_ID.search(text or "")
    if match:
        return match.group(0).upper()
    return ""


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


def build_metadata_filter_qrels(df: pd.DataFrame, queries: pd.DataFrame) -> Dict[int, List[str]]:
    rows_by_id = {str(row.get("id", "")): row for _, row in df.iterrows()}

    indexed_rows = []
    for _, row in df.iterrows():
        indexed_rows.append(
            {
                "id": str(row.get("id", "")),
                "topics": _label_set(row.get("topic", "")),
                "countries": _label_set(row.get("country", "")),
                "years": _year_range(row.get("time_collection_years", "")),
            }
        )

    qrels_map: Dict[int, List[str]] = {}
    for _, query in queries.iterrows():
        query_id = int(query["query_id"])
        source_id = str(query.get("source_dataset_id", ""))
        variant = str(query.get("query_variant", ""))
        source_row = rows_by_id.get(source_id)

        if variant == "V3_TITLE_ONLY":
            if source_row is not None:
                qrels_map[query_id] = [source_id]
            continue

        query_topics = _label_set(query.get("query_topics", ""))
        query_countries = _label_set(query.get("query_countries", ""))
        query_years = _year_range(query.get("query_time_collection_years", ""))

        if not query_topics and source_row is not None:
            query_topics = _label_set(source_row.get("topic", ""))
        if not query_countries and source_row is not None:
            query_countries = _label_set(source_row.get("country", ""))
        if query_years is None and source_row is not None:
            query_years = _year_range(source_row.get("time_collection_years", ""))

        if not query_topics or not query_countries or query_years is None:
            continue

        relevant_ids = []
        for row in indexed_rows:
            if not row["id"]:
                continue
            if not (query_topics & row["topics"]):
                continue
            if not (query_countries & row["countries"]):
                continue
            if not _ranges_overlap(query_years, row["years"]):
                continue
            relevant_ids.append(row["id"])

        if not relevant_ids and source_row is not None and source_id:
            relevant_ids.append(source_id)

        if relevant_ids:
            qrels_map[query_id] = relevant_ids

    return qrels_map


def metadata_filter_debug_frame(df: pd.DataFrame, queries: pd.DataFrame, qrels_map: Dict[int, List[str]]) -> pd.DataFrame:
    ids = {str(row.get("id", "")) for _, row in df.iterrows()}
    rows = []
    for _, query in queries.iterrows():
        query_id = int(query["query_id"])
        source_id = str(query.get("source_dataset_id", ""))
        query_topics = _label_set(query.get("query_topics", ""))
        query_countries = _label_set(query.get("query_countries", ""))
        query_years = _year_range(query.get("query_time_collection_years", ""))
        rows.append(
            {
                "query_id": query_id,
                "query_variant": str(query.get("query_variant", "")),
                "source_dataset_id": source_id,
                "source_id_in_eval_metadata": source_id in ids,
                "query_topics_count": len(query_topics),
                "query_countries_count": len(query_countries),
                "query_years": "" if query_years is None else f"{query_years[0]}-{query_years[1]}",
                "qrels_count": len(qrels_map.get(query_id, [])),
                "query_topics_raw": str(query.get("query_topics", "")),
                "query_countries_raw": str(query.get("query_countries", "")),
                "query_time_collection_years_raw": str(query.get("query_time_collection_years", "")),
            }
        )
    return pd.DataFrame(rows)


def qrels_to_frame(qrels_map: Dict[int, List[str]], df: pd.DataFrame, queries: pd.DataFrame) -> pd.DataFrame:
    metadata_by_id = {
        str(row.get("id", "")): {
            "relevant_title": str(row.get("title", "")),
            "relevant_topic": str(row.get("topic", "")),
            "relevant_country": str(row.get("country", "")),
            "relevant_time_collection_years": str(row.get("time_collection_years", "")),
        }
        for _, row in df.iterrows()
    }
    query_meta = {
        int(row["query_id"]): {
            "query_variant": str(row.get("query_variant", "")),
            "source_dataset_id": str(row.get("source_dataset_id", "")),
            "source_title": str(row.get("source_title", "")),
            "query_text": str(row.get("query_text", "")),
            "query_topics": str(row.get("query_topics", "")),
            "query_countries": str(row.get("query_countries", "")),
            "query_time_collection_years": str(row.get("query_time_collection_years", "")),
        }
        for _, row in queries.iterrows()
    }

    rows = []
    for query_id, relevant_ids in qrels_map.items():
        qinfo = query_meta.get(int(query_id), {})
        for relevant_id in relevant_ids:
            rows.append(
                {
                    "query_id": int(query_id),
                    **qinfo,
                    "relevant_dataset_id": relevant_id,
                    **metadata_by_id.get(str(relevant_id), {}),
                }
            )

    return pd.DataFrame(rows)


def match_items(
    results: pd.DataFrame, df: pd.DataFrame
) -> Tuple[pd.DataFrame, Dict[str, str], Dict[str, str]]:
    doi_to_id = {}
    portal_to_id = {}
    dataset_id_to_id = {}

    for _, row in df.iterrows():
        did = str(row.get("id", ""))
        doi = _normalize_doi(str(row.get("doi", "")))
        portal = _normalize_url(str(row.get("portal_url", "")))
        dataset_id = _extract_dataset_id(did)
        if doi:
            doi_to_id[doi] = did
        if portal:
            portal_to_id[portal] = did
        if dataset_id:
            dataset_id_to_id[dataset_id] = did

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
                dataset_id = _extract_dataset_id(link_or_doi)
                if dataset_id and dataset_id in dataset_id_to_id:
                    matched_id = dataset_id_to_id[dataset_id]
                    confidence = 1.0
                elif title:
                    best = _best_title_match(title, titles)
                    if best:
                        score, idx = best
                        if score >= 70:
                            matched_id = ids[idx]
                            confidence = float(score) / 100.0

        link_valid = False
        if doi:
            link_valid = doi in doi_to_id
        else:
            portal = _normalize_url(link_or_doi)
            dataset_id = _extract_dataset_id(link_or_doi)
            link_valid = portal in portal_to_id or dataset_id in dataset_id_to_id

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
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    per_query_rows = []
    metrics_rows = []

    group_cols = ["query_id", "query_variant", "mode"]
    if "model" in results.columns:
        group_cols.append("model")

    for group_key, group in results.groupby(group_cols, sort=False):
        if len(group_cols) == 4:
            query_id, variant, mode, model = group_key
        else:
            query_id, variant, mode = group_key
            model = ""
        query_id = int(query_id)
        if query_id not in qrels_map:
            continue
        relevant_ids = set(qrels_map[query_id])
        group = group.sort_values("rank")

        matched_ids = group["matched_dataset_id"].tolist()
        link_valids = group["link_valid"].tolist()

        rels = []
        credited_relevant_ids = set()
        for i in range(top_k):
            if (
                i < len(matched_ids)
                and matched_ids[i] in relevant_ids
                and matched_ids[i] not in credited_relevant_ids
            ):
                rels.append(1)
                credited_relevant_ids.add(matched_ids[i])
            else:
                rels.append(0)

        relevant_retrieved = sum(rels)
        hit = 1 if relevant_retrieved > 0 else 0
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
                "model": model,
                "hit_at_k": hit,
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
                "model",
                "hit_at_k",
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
            metrics_per_query.groupby(["query_variant", "mode", "model"], sort=False)
            .agg(
                precision_at_k=("precision_at_k", "mean"),
                hit_at_k=("hit_at_k", "mean"),
                recall_at_k=("recall_at_k", "mean"),
                mrr=("mrr", "mean"),
                ndcg_at_k=("ndcg_at_k", "mean"),
                link_valid_rate=("link_valid_rate", "mean"),
                off_repo_rate=("off_repo_rate", "mean"),
            )
            .reset_index()
        )

    return per_query, summary, metrics_per_query


def match_and_eval(config_path: str) -> None:
    cfg = load_config(config_path)
    output_dir = Path(cfg.get("output_dir", "."))
    output_dir.mkdir(parents=True, exist_ok=True)

    results_path = output_dir / "llm_results.csv"
    if not results_path.exists():
        raise FileNotFoundError("llm_results.csv not found. Run run_llm first.")

    results = pd.read_csv(results_path)
    queries = pd.read_csv(output_dir / "queries.csv")
    eval_input_path = cfg.get("qrels_input_path", cfg["input_path"])
    eval_input_format = cfg.get("qrels_input_format", cfg.get("input_format", "csv"))
    df = load_metadata(eval_input_path, eval_input_format)

    qrels_strategy = str(cfg.get("qrels_strategy", "silver")).strip().lower()
    if qrels_strategy == "metadata_filter":
        qrels_map = build_metadata_filter_qrels(df, queries)
    elif qrels_strategy == "silver":
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
    else:
        raise ValueError(f"Unsupported qrels_strategy: {qrels_strategy}")

    qrels_to_frame(qrels_map, df, queries).to_csv(output_dir / "qrels.csv", index=False)
    if qrels_strategy == "metadata_filter":
        metadata_filter_debug_frame(df, queries, qrels_map).to_csv(
            output_dir / "qrels_debug.csv",
            index=False,
        )

    results, _, _ = match_items(results, df)

    top_k = int(cfg.get("top_k_return", 10))
    per_query, summary, metrics_per_query = compute_metrics(results, qrels_map, top_k)

    per_query.to_csv(output_dir / "per_query_results.csv", index=False)
    metrics_per_query.to_csv(output_dir / "metrics_per_query.csv", index=False)
    summary.to_csv(output_dir / "metrics_summary.csv", index=False)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, help="Path to config.yaml")
    args = parser.parse_args()
    match_and_eval(args.config)


if __name__ == "__main__":
    main()
