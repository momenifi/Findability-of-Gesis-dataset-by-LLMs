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
from .config_paths import apply_variant_override, resolve_output_dir

RE_DOI = re.compile(r"10\.\d{4,9}/\S+", re.IGNORECASE)
RE_ZA_ID = re.compile(r"\bZA\d+\b", re.IGNORECASE)
OUTPUT_CSV_SEP = ";"
IDENTIFIER_MATCH_METHODS = {"doi", "portal_url", "dataset_id"}
TITLE_MATCH_METHODS = {"title_exact", "title_fuzzy"}
TITLE_COLUMNS = [
    "title",
    "study_title",
    "other_titles",
    "study_title_en",
    "title_en",
    "other_titles_en",
]
GLOBAL_TITLE_FUZZY_LIMIT = 50000


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


def _year_range_from_text(*values: object) -> Tuple[int, int] | None:
    years = []
    for value in values:
        text = str(value or "")
        years.extend(int(match.group(0)) for match in re.finditer(r"\b(18|19|20)\d{2}\b", text))
    if not years:
        return None
    return min(years), max(years)


def _ranges_overlap(left: Tuple[int, int] | None, right: Tuple[int, int] | None) -> bool:
    if left is None or right is None:
        return False
    return left[0] <= right[1] and right[0] <= left[1]


def _tokens(value: str) -> set[str]:
    stopwords = {
        "and",
        "or",
        "the",
        "of",
        "in",
        "to",
        "for",
        "with",
        "about",
        "during",
        "data",
        "dataset",
        "datasets",
        "survey",
        "study",
        "studies",
    }
    return {
        token
        for token in re.findall(r"[a-zA-Z][a-zA-Z-]{2,}", _normalize_label(value))
        if token not in stopwords
    }


def _topic_text_matches(query_topics: set[str], row_text: str) -> bool:
    row_tokens = _tokens(row_text)
    if not row_tokens:
        return False
    for topic in query_topics:
        topic_tokens = _tokens(topic)
        if not topic_tokens:
            continue
        if topic_tokens & row_tokens:
            return True
    return False


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


def _build_title_index(df: pd.DataFrame) -> Tuple[List[str], List[str], List[str], Dict[str, List[Tuple[str, str]]], Dict[str, int]]:
    titles = []
    ids = []
    columns = []
    titles_by_id = {}
    exact_title_to_idx = {}
    seen = set()

    for _, row in df.iterrows():
        did = str(row.get("id", ""))
        if not did:
            continue
        for column in TITLE_COLUMNS:
            if column not in df.columns:
                continue
            for title in _parse_list_value(row.get(column, "")):
                title_norm = _normalize_label(title)
                key = (did, title_norm)
                if not title_norm or key in seen:
                    continue
                seen.add(key)
                exact_title_to_idx.setdefault(title_norm, len(titles))
                titles_by_id.setdefault(did, []).append((title, column))
                titles.append(title)
                ids.append(did)
                columns.append(column)

    return titles, ids, columns, titles_by_id, exact_title_to_idx


def _best_dataset_title_match(title: str, candidates: List[Tuple[str, str]]) -> Tuple[float, str] | None:
    candidate_titles = [candidate_title for candidate_title, _ in candidates]
    best = _best_title_match(title, candidate_titles)
    if not best:
        return None
    score, idx = best
    return score, candidates[idx][1]


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


def _normalize_dois(raw: str) -> list[str]:
    text = (raw or "").strip()
    if not text:
        return []

    values = []
    if text.startswith("[") and text.endswith("]"):
        try:
            parsed = ast.literal_eval(text)
            if isinstance(parsed, list):
                values = [str(item).strip() for item in parsed if str(item).strip()]
        except (ValueError, SyntaxError):
            values = []

    if not values:
        values = [text]

    dois = []
    for value in values:
        doi = _normalize_doi(value)
        if doi and doi not in dois:
            dois.append(doi)
    return dois


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
        search_text = _normalize_label(
            " ".join(
                str(row.get(field, "") or "")
                for field in [
                    "title",
                    "abstract",
                    "content_description",
                    "topics_stw",
                    "topics_thesoz",
                    "categories",
                ]
            )
        )
        years = _year_range(row.get("time_collection_years", ""))
        if years is None:
            years = _year_range_from_text(search_text)
        indexed_rows.append(
            {
                "id": str(row.get("id", "")),
                "topics": _label_set(row.get("topic", "")),
                "countries": _label_set(row.get("country", "")),
                "years": years,
                "universes": _label_set(row.get("universe", "")),
                "analysis_units": _label_set(row.get("analysis_unit", "")),
                "search_text": search_text,
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
        query_universes = _label_set(query.get("query_universe", ""))
        query_analysis_units = _label_set(query.get("query_analysis_units", ""))

        if not query_topics and source_row is not None:
            query_topics = _label_set(source_row.get("topic", ""))
        if not query_countries and source_row is not None:
            query_countries = _label_set(source_row.get("country", ""))
        if query_years is None and source_row is not None:
            query_years = _year_range(source_row.get("time_collection_years", ""))

        universe_variant = variant in {
            "V4_TOPIC_COUNTRY_TIME_UNIVERSE_ANALYSIS_UNIT_ALL_TOPICS",
            "V5_TOPIC_COUNTRY_TIME_UNIVERSE_ALL_TOPICS",
        }
        analysis_unit_variant = (
            variant == "V4_TOPIC_COUNTRY_TIME_UNIVERSE_ANALYSIS_UNIT_ALL_TOPICS"
        )
        if universe_variant and source_row is not None:
            if not query_universes:
                query_universes = _label_set(source_row.get("universe", ""))
        if analysis_unit_variant and source_row is not None:
            if not query_analysis_units:
                query_analysis_units = _label_set(source_row.get("analysis_unit", ""))

        if not query_topics or not query_countries or query_years is None:
            continue
        if universe_variant and not query_universes:
            continue
        if analysis_unit_variant and not query_analysis_units:
            continue

        relevant_ids = []
        for row in indexed_rows:
            if not row["id"]:
                continue
            topic_match = bool(query_topics & row["topics"]) or _topic_text_matches(
                query_topics,
                row["search_text"],
            )
            if not topic_match:
                continue
            if not (query_countries & row["countries"]):
                continue
            if not _ranges_overlap(query_years, row["years"]):
                continue
            if universe_variant and not (query_universes & row["universes"]):
                continue
            if analysis_unit_variant and not (query_analysis_units & row["analysis_units"]):
                continue
            relevant_ids.append(row["id"])

        if source_row is not None and source_id and source_id not in relevant_ids:
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
        query_universes = _label_set(query.get("query_universe", ""))
        query_analysis_units = _label_set(query.get("query_analysis_units", ""))
        rows.append(
            {
                "query_id": query_id,
                "query_variant": str(query.get("query_variant", "")),
                "source_dataset_id": source_id,
                "source_id_in_eval_metadata": source_id in ids,
                "query_topics_count": len(query_topics),
                "query_countries_count": len(query_countries),
                "query_years": "" if query_years is None else f"{query_years[0]}-{query_years[1]}",
                "query_universe_count": len(query_universes),
                "query_analysis_units_count": len(query_analysis_units),
                "qrels_count": len(qrels_map.get(query_id, [])),
                "query_topics_raw": str(query.get("query_topics", "")),
                "query_countries_raw": str(query.get("query_countries", "")),
                "query_time_collection_years_raw": str(query.get("query_time_collection_years", "")),
                "query_universe_raw": str(query.get("query_universe", "")),
                "query_analysis_units_raw": str(query.get("query_analysis_units", "")),
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
            "relevant_universe": str(row.get("universe", "")),
            "relevant_analysis_unit": str(row.get("analysis_unit", "")),
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
            "query_universe": str(row.get("query_universe", "")),
            "query_analysis_units": str(row.get("query_analysis_units", "")),
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
        dois = _normalize_dois(str(row.get("doi", "")))
        portal = _normalize_url(str(row.get("portal_url", "")))
        dataset_id = _extract_dataset_id(did)
        for doi in dois:
            doi_to_id[doi] = did
        if portal:
            portal_to_id[portal] = did
        if dataset_id:
            dataset_id_to_id[dataset_id] = did

    titles, title_ids, title_columns, titles_by_id, exact_title_to_idx = _build_title_index(df)

    matched_ids = []
    confidences = []
    link_valids = []
    match_methods = []
    title_matched_ids = []
    title_match_scores = []
    title_match_methods = []
    title_match_columns = []

    for _, row in results.iterrows():
        link_or_doi = str(row.get("returned_url_or_doi", ""))
        title = str(row.get("returned_title", ""))

        matched_id = ""
        confidence = 0.0
        match_method = "unmatched"
        doi = _extract_doi(link_or_doi)
        if doi and doi in doi_to_id:
            matched_id = doi_to_id[doi]
            confidence = 1.0
            match_method = "doi"
        else:
            portal = _normalize_url(link_or_doi)
            if portal in portal_to_id:
                matched_id = portal_to_id[portal]
                confidence = 1.0
                match_method = "portal_url"
            else:
                dataset_id = _extract_dataset_id(link_or_doi)
                if dataset_id and dataset_id in dataset_id_to_id:
                    matched_id = dataset_id_to_id[dataset_id]
                    confidence = 1.0
                    match_method = "dataset_id"

        title_matched_id = ""
        title_match_score = 0.0
        title_match_method = "unmatched"
        title_match_column = ""

        if title:
            if matched_id and matched_id in titles_by_id:
                best = _best_dataset_title_match(title, titles_by_id[matched_id])
                if best:
                    score, column = best
                    if score >= 70:
                        title_matched_id = matched_id
                        title_match_score = float(score) / 100.0
                        title_match_method = "title_exact" if score >= 99.999 else "title_fuzzy"
                        title_match_column = column

            if not title_matched_id:
                title_norm = _normalize_label(title)
                idx = exact_title_to_idx.get(title_norm)
                if idx is not None:
                    title_matched_id = title_ids[idx]
                    title_match_score = 1.0
                    title_match_method = "title_exact"
                    title_match_column = title_columns[idx]

            if not title_matched_id and titles and len(titles) <= GLOBAL_TITLE_FUZZY_LIMIT:
                best = _best_title_match(title, titles)
                if best:
                    score, idx = best
                    if score >= 70:
                        title_matched_id = title_ids[idx]
                        title_match_score = float(score) / 100.0
                        title_match_method = "title_exact" if score >= 99.999 else "title_fuzzy"
                        title_match_column = title_columns[idx]

        if not matched_id and title_matched_id:
            matched_id = title_matched_id
            confidence = title_match_score
            match_method = title_match_method

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
        match_methods.append(match_method)
        title_matched_ids.append(title_matched_id)
        title_match_scores.append(title_match_score)
        title_match_methods.append(title_match_method)
        title_match_columns.append(title_match_column)

    results = results.copy()
    results["matched_dataset_id"] = matched_ids
    results["match_confidence"] = confidences
    results["link_valid"] = link_valids
    results["match_method"] = match_methods
    results["title_matched_dataset_id"] = title_matched_ids
    results["title_match_score"] = title_match_scores
    results["title_match_method"] = title_match_methods
    results["title_match_column"] = title_match_columns
    results["is_identifier_match"] = results["match_method"].isin(IDENTIFIER_MATCH_METHODS).astype(int)
    return results, doi_to_id, portal_to_id


def _ranking_metrics(rels: list[int], relevant_count: int, top_k: int) -> dict:
    relevant_retrieved = sum(rels)
    hit = 1 if relevant_retrieved > 0 else 0
    precision = relevant_retrieved / float(top_k)
    recall = relevant_retrieved / float(relevant_count or 1)

    mrr = 0.0
    for idx, rel in enumerate(rels[:top_k], start=1):
        if rel:
            mrr = 1.0 / idx
            break

    dcg = 0.0
    for i, rel in enumerate(rels, start=1):
        if rel:
            dcg += 1.0 / math.log2(i + 1)

    ideal_rels = [1] * min(relevant_count, top_k)
    idcg = 0.0
    for i, rel in enumerate(ideal_rels, start=1):
        if rel:
            idcg += 1.0 / math.log2(i + 1)

    return {
        "hit": hit,
        "precision": precision,
        "recall": recall,
        "mrr": mrr,
        "ndcg": dcg / idcg if idcg > 0 else 0.0,
    }


def compute_metrics(
    results: pd.DataFrame, qrels_map: Dict[int, List[str]], top_k: int, source_id_by_query: Dict[int, str] | None = None
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    per_query_rows = []
    metrics_rows = []
    source_id_by_query = source_id_by_query or {}

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
        source_id = str(source_id_by_query.get(query_id, ""))
        group = group.sort_values("rank")

        matched_ids = group["matched_dataset_id"].tolist()
        link_valids = group["link_valid"].tolist()
        match_methods = group["match_method"].tolist()
        title_matched_ids = group["title_matched_dataset_id"].tolist()
        title_match_methods = group["title_match_method"].tolist()

        rels = []
        strict_rels = []
        title_rels = []
        source_rels = []
        strict_source_rels = []
        title_source_rels = []
        credited_relevant_ids = set()
        credited_strict_relevant_ids = set()
        credited_title_relevant_ids = set()
        credited_source = False
        credited_strict_source = False
        credited_title_source = False
        for i in range(top_k):
            matched_id = matched_ids[i] if i < len(matched_ids) else ""
            match_method = match_methods[i] if i < len(match_methods) else "unmatched"
            title_matched_id = title_matched_ids[i] if i < len(title_matched_ids) else ""
            title_match_method = title_match_methods[i] if i < len(title_match_methods) else "unmatched"
            is_source = bool(source_id and matched_id == source_id)
            is_title_source = bool(source_id and title_matched_id == source_id)
            if (
                matched_id in relevant_ids
                and matched_id not in credited_relevant_ids
            ):
                rels.append(1)
                credited_relevant_ids.add(matched_id)
            else:
                rels.append(0)

            if (
                matched_id in relevant_ids
                and match_method in IDENTIFIER_MATCH_METHODS
                and matched_id not in credited_strict_relevant_ids
            ):
                strict_rels.append(1)
                credited_strict_relevant_ids.add(matched_id)
            else:
                strict_rels.append(0)

            if (
                title_matched_id in relevant_ids
                and title_match_method in TITLE_MATCH_METHODS
                and title_matched_id not in credited_title_relevant_ids
            ):
                title_rels.append(1)
                credited_title_relevant_ids.add(title_matched_id)
            else:
                title_rels.append(0)

            if is_source and not credited_source:
                source_rels.append(1)
                credited_source = True
            else:
                source_rels.append(0)

            if (
                is_source
                and match_method in IDENTIFIER_MATCH_METHODS
                and not credited_strict_source
            ):
                strict_source_rels.append(1)
                credited_strict_source = True
            else:
                strict_source_rels.append(0)

            if (
                is_title_source
                and title_match_method in TITLE_MATCH_METHODS
                and not credited_title_source
            ):
                title_source_rels.append(1)
                credited_title_source = True
            else:
                title_source_rels.append(0)

        broad_metrics = _ranking_metrics(rels, len(relevant_ids), top_k)
        strict_metrics = _ranking_metrics(strict_rels, len(relevant_ids), top_k)
        title_metrics = _ranking_metrics(title_rels, len(relevant_ids), top_k)
        source_metrics = _ranking_metrics(source_rels, 1 if source_id else 0, top_k)
        strict_source_metrics = _ranking_metrics(strict_source_rels, 1 if source_id else 0, top_k)
        title_source_metrics = _ranking_metrics(title_source_rels, 1 if source_id else 0, top_k)

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
                "hit_at_k": broad_metrics["hit"],
                "precision_at_k": broad_metrics["precision"],
                "recall_at_k": broad_metrics["recall"],
                "mrr": broad_metrics["mrr"],
                "ndcg_at_k": broad_metrics["ndcg"],
                "strict_hit_at_k": strict_metrics["hit"],
                "strict_precision_at_k": strict_metrics["precision"],
                "strict_recall_at_k": strict_metrics["recall"],
                "strict_mrr": strict_metrics["mrr"],
                "strict_ndcg_at_k": strict_metrics["ndcg"],
                "title_match_hit_at_k": title_metrics["hit"],
                "title_match_precision_at_k": title_metrics["precision"],
                "title_match_recall_at_k": title_metrics["recall"],
                "title_match_mrr": title_metrics["mrr"],
                "title_match_ndcg_at_k": title_metrics["ndcg"],
                "source_hit_at_k": source_metrics["hit"],
                "source_mrr": source_metrics["mrr"],
                "source_ndcg_at_k": source_metrics["ndcg"],
                "strict_source_hit_at_k": strict_source_metrics["hit"],
                "strict_source_mrr": strict_source_metrics["mrr"],
                "strict_source_ndcg_at_k": strict_source_metrics["ndcg"],
                "title_source_hit_at_k": title_source_metrics["hit"],
                "title_source_mrr": title_source_metrics["mrr"],
                "title_source_ndcg_at_k": title_source_metrics["ndcg"],
                "gesis_relevant_hit_at_k": broad_metrics["hit"],
                "strict_gesis_relevant_hit_at_k": strict_metrics["hit"],
                "title_gesis_relevant_hit_at_k": title_metrics["hit"],
                "link_valid_rate": link_valid_rate,
                "off_repo_rate": off_repo_rate,
            }
        )

        for _, row in group.iterrows():
            per_query_rows.append(
                {
                    **row.to_dict(),
                    "source_dataset_id_for_query": source_id,
                    "is_source_dataset": int(source_id and row["matched_dataset_id"] == source_id),
                    "is_strict_source_dataset": int(
                        source_id
                        and row["matched_dataset_id"] == source_id
                        and row["match_method"] in IDENTIFIER_MATCH_METHODS
                    ),
                    "is_title_source_dataset": int(
                        source_id
                        and row["title_matched_dataset_id"] == source_id
                        and row["title_match_method"] in TITLE_MATCH_METHODS
                    ),
                    "is_relevant": int(row["matched_dataset_id"] in relevant_ids),
                    "is_gesis_relevant_dataset": int(row["matched_dataset_id"] in relevant_ids),
                    "is_strict_relevant": int(
                        row["matched_dataset_id"] in relevant_ids
                        and row["match_method"] in IDENTIFIER_MATCH_METHODS
                    ),
                    "is_strict_gesis_relevant_dataset": int(
                        row["matched_dataset_id"] in relevant_ids
                        and row["match_method"] in IDENTIFIER_MATCH_METHODS
                    ),
                    "is_title_match_relevant": int(
                        row["title_matched_dataset_id"] in relevant_ids
                        and row["title_match_method"] in TITLE_MATCH_METHODS
                    ),
                    "is_title_gesis_relevant_dataset": int(
                        row["title_matched_dataset_id"] in relevant_ids
                        and row["title_match_method"] in TITLE_MATCH_METHODS
                    ),
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
                "strict_hit_at_k",
                "strict_precision_at_k",
                "strict_recall_at_k",
                "strict_mrr",
                "strict_ndcg_at_k",
                "title_match_hit_at_k",
                "title_match_precision_at_k",
                "title_match_recall_at_k",
                "title_match_mrr",
                "title_match_ndcg_at_k",
                "source_hit_at_k",
                "source_mrr",
                "source_ndcg_at_k",
                "strict_source_hit_at_k",
                "strict_source_mrr",
                "strict_source_ndcg_at_k",
                "title_source_hit_at_k",
                "title_source_mrr",
                "title_source_ndcg_at_k",
                "gesis_relevant_hit_at_k",
                "strict_gesis_relevant_hit_at_k",
                "title_gesis_relevant_hit_at_k",
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
                strict_precision_at_k=("strict_precision_at_k", "mean"),
                strict_hit_at_k=("strict_hit_at_k", "mean"),
                strict_recall_at_k=("strict_recall_at_k", "mean"),
                strict_mrr=("strict_mrr", "mean"),
                strict_ndcg_at_k=("strict_ndcg_at_k", "mean"),
                title_match_precision_at_k=("title_match_precision_at_k", "mean"),
                title_match_hit_at_k=("title_match_hit_at_k", "mean"),
                title_match_recall_at_k=("title_match_recall_at_k", "mean"),
                title_match_mrr=("title_match_mrr", "mean"),
                title_match_ndcg_at_k=("title_match_ndcg_at_k", "mean"),
                source_hit_at_k=("source_hit_at_k", "mean"),
                source_mrr=("source_mrr", "mean"),
                source_ndcg_at_k=("source_ndcg_at_k", "mean"),
                strict_source_hit_at_k=("strict_source_hit_at_k", "mean"),
                strict_source_mrr=("strict_source_mrr", "mean"),
                strict_source_ndcg_at_k=("strict_source_ndcg_at_k", "mean"),
                title_source_hit_at_k=("title_source_hit_at_k", "mean"),
                title_source_mrr=("title_source_mrr", "mean"),
                title_source_ndcg_at_k=("title_source_ndcg_at_k", "mean"),
                gesis_relevant_hit_at_k=("gesis_relevant_hit_at_k", "mean"),
                strict_gesis_relevant_hit_at_k=("strict_gesis_relevant_hit_at_k", "mean"),
                title_gesis_relevant_hit_at_k=("title_gesis_relevant_hit_at_k", "mean"),
                link_valid_rate=("link_valid_rate", "mean"),
                off_repo_rate=("off_repo_rate", "mean"),
            )
            .reset_index()
        )

    return per_query, summary, metrics_per_query


def match_and_eval(config_path: str, variant: str | None = None) -> None:
    cfg = apply_variant_override(load_config(config_path), variant)
    output_dir = resolve_output_dir(cfg)
    output_dir.mkdir(parents=True, exist_ok=True)

    results_path = output_dir / "llm_results.csv"
    if not results_path.exists():
        raise FileNotFoundError("llm_results.csv not found. Run run_llm first.")

    results = pd.read_csv(results_path, sep=None, engine="python")
    queries = pd.read_csv(output_dir / "queries.csv", sep=None, engine="python")
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

    qrels_to_frame(qrels_map, df, queries).to_csv(output_dir / "qrels.csv", index=False, sep=OUTPUT_CSV_SEP)
    if qrels_strategy == "metadata_filter":
        metadata_filter_debug_frame(df, queries, qrels_map).to_csv(
            output_dir / "qrels_debug.csv",
            index=False,
            sep=OUTPUT_CSV_SEP,
        )

    results, _, _ = match_items(results, df)

    top_k = int(cfg.get("top_k_return", 10))
    source_id_by_query = {
        int(row["query_id"]): str(row.get("source_dataset_id", ""))
        for _, row in queries.iterrows()
    }
    per_query, summary, metrics_per_query = compute_metrics(results, qrels_map, top_k, source_id_by_query)

    per_query.to_csv(output_dir / "per_query_results.csv", index=False, sep=OUTPUT_CSV_SEP)
    metrics_per_query.to_csv(output_dir / "metrics_per_query.csv", index=False, sep=OUTPUT_CSV_SEP)
    summary.to_csv(output_dir / "metrics_summary.csv", index=False, sep=OUTPUT_CSV_SEP)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, help="Path to config.yaml")
    parser.add_argument("-V", "--variant", help="Override query variant (V1, V2, V3, V4, V5, or V6)")
    args = parser.parse_args()
    match_and_eval(args.config, args.variant)


if __name__ == "__main__":
    main()
