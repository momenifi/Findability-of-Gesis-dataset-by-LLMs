import re
from typing import Optional

import pandas as pd

RE_DOI = re.compile(r"10\.\d{4,9}/\S+", re.IGNORECASE)


def _safe_str(value: Optional[object]) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    return str(value).strip()


def _coalesce_series(primary: pd.Series, fallback: pd.Series) -> pd.Series:
    p = primary.fillna("").astype(str)
    f = fallback.fillna("").astype(str)
    mask = p.str.strip() == ""
    out = p.copy()
    out[mask] = f[mask]
    return out.fillna("")


def _normalize_doi(raw: Optional[object]) -> str:
    doi = _safe_str(raw)
    if not doi:
        return ""
    doi = doi.strip()
    doi = re.sub(r"^doi:\s*", "", doi, flags=re.IGNORECASE)
    doi = doi.replace("https://doi.org/", "").replace("http://doi.org/", "")
    doi = doi.replace("https://dx.doi.org/", "").replace("http://dx.doi.org/", "")
    doi = doi.strip().strip("<>")
    return doi


def _is_doi(value: str) -> bool:
    return bool(RE_DOI.search(value or ""))


def _normalize_url(raw: Optional[object]) -> str:
    url = _safe_str(raw)
    if not url:
        return ""
    return url.strip()


def load_metadata(input_path: str, input_format: str) -> pd.DataFrame:
    if input_format.lower() == "csv":
        df = pd.read_csv(input_path)
    elif input_format.lower() == "jsonl":
        df = pd.read_json(input_path, lines=True)
    else:
        raise ValueError(f"Unsupported input_format: {input_format}")

    # Ensure base columns exist
    for col in ["id", "portal_url", "doi", "handle"]:
        if col not in df.columns:
            df[col] = ""

    def col_or_empty(name: str) -> pd.Series:
        if name in df.columns:
            return df[name]
        return pd.Series([""] * len(df))

    fallback_map = {
        "title": ("title_en", "title"),
        "abstract": ("abstract_en", "abstract"),
        "topic": ("topic_en", "topic"),
        "methodology": ("methodology_collection_en", "methodology_collection"),
        "country": ("countries_collection_en", "countries_collection"),
        "time_collection_years": ("time_collection_years_en", "time_collection_years"),
        "universe": ("universe_en", "universe"),
        "content_description": ("content_description_en", "content_description"),
        "topics_stw": ("topics_STW_en", "topics_STW"),
        "topics_thesoz": ("topics_TheSoz_en", "topics_TheSoz"),
        "categories": ("categories_en", "category"),
    }

    for new_col, (primary, fallback) in fallback_map.items():
        df[new_col] = _coalesce_series(col_or_empty(primary), col_or_empty(fallback))

    df["portal_url"] = df["portal_url"].fillna("").astype(str).str.strip()
    df["doi"] = df["doi"].fillna("").astype(str).str.strip()
    df["id"] = df["id"].fillna("").astype(str).str.strip()
    df["handle"] = df["handle"].fillna("").astype(str).str.strip()

    def build_link(row) -> str:
        portal = _normalize_url(row.get("portal_url", ""))
        if portal:
            return portal
        doi_raw = _normalize_doi(row.get("doi", ""))
        if doi_raw and _is_doi(doi_raw):
            return f"https://doi.org/{doi_raw}"
        return ""

    df["link"] = df.apply(build_link, axis=1)

    # Final required columns
    required_cols = [
        "id",
        "portal_url",
        "doi",
        "handle",
        "link",
        "title",
        "abstract",
        "topic",
        "methodology",
        "country",
        "time_collection_years",
        "universe",
        "content_description",
        "topics_stw",
        "topics_thesoz",
        "categories",
    ]

    for col in required_cols:
        if col not in df.columns:
            df[col] = ""

    return df[required_cols]


__all__ = ["load_metadata"]
