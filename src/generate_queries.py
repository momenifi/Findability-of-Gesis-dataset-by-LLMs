import argparse
import ast
import json
import re
from pathlib import Path

import pandas as pd
import yaml

from .load_metadata import load_metadata

RE_DOI = re.compile(r"10\.\d{4,9}/\S+", re.IGNORECASE)

QUERY_TEMPLATE = "Can you find datasets related to [{topic}] in [{country}] during the [{time_collection_years}]?"
TITLE_QUERY_TEMPLATE = "Can you find the dataset titled [{title}]?"

VARIANTS = {
    "V1_TOPIC_COUNTRY_TIME_ALL_TOPICS": "all_topics",
    "V2_TOPIC_COUNTRY_TIME_SINGLE_TOPIC": "single_topic",
    "V3_TITLE_ONLY": "title",
}


def _normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _normalize_query(text: str) -> str:
    return _normalize_whitespace(text).lower()


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


def _format_list_value(values: list[str]) -> str:
    if not values:
        return ""
    return json.dumps(values, ensure_ascii=False)


def _extract_years(values: list[str]) -> list[int]:
    years = []
    for value in values:
        years.extend(int(match.group(0)) for match in re.finditer(r"\b\d{4}\b", value))
    return years


def _format_time_value(years: list[str], time_format: str) -> str:
    if time_format == "years":
        return _format_list_value(years)

    numeric_years = _extract_years(years)
    if not numeric_years:
        return _format_list_value(years)

    start = min(numeric_years)
    end = max(numeric_years)

    if time_format == "span":
        return str(start) if start == end else f"{start}-{end}"

    if time_format == "decade":
        decades = sorted({(year // 10) * 10 for year in range(start, end + 1)})
        if len(decades) == 1:
            return f"{decades[0]}s"
        return " and ".join(f"{decade}s" for decade in decades)

    raise ValueError(f"Unsupported time_format: {time_format}")


def _contains_identifiers(query: str, row: pd.Series) -> bool:
    q = (query or "").lower()
    for field in ["id", "doi", "handle"]:
        val = str(row.get(field, "") or "").strip().lower()
        if val and val in q:
            return True
    if RE_DOI.search(query or ""):
        return True
    return False


def load_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _build_queries_for_row(row: pd.Series, variant: str, time_format: str) -> list[dict]:
    topics = _parse_list_value(row.get("topic", ""))
    titles = _parse_list_value(row.get("title", ""))
    countries = _parse_list_value(row.get("country", ""))
    years = _parse_list_value(row.get("time_collection_years", ""))

    if variant == "V1_TOPIC_COUNTRY_TIME_ALL_TOPICS":
        if not topics or not countries or not years:
            return []
        country_text = _format_list_value(countries)
        years_text = _format_time_value(years, time_format)
        years_qrels_text = _format_list_value(years)
        topic_text = _format_list_value(topics)
        return [
            {
                "query_text": QUERY_TEMPLATE.format(
                    topic=topic_text,
                    country=country_text,
                    time_collection_years=years_text,
                ),
                "query_topics": topic_text,
                "query_countries": country_text,
                "query_time_collection_years": years_qrels_text,
                "query_time_display": years_text,
            }
        ]

    if variant == "V2_TOPIC_COUNTRY_TIME_SINGLE_TOPIC":
        if not topics or not countries or not years:
            return []
        country_text = _format_list_value(countries)
        years_text = _format_time_value(years, time_format)
        years_qrels_text = _format_list_value(years)
        queries = []
        for topic in topics:
            queries.append(
                {
                    "query_text": QUERY_TEMPLATE.format(
                        topic=_format_list_value([topic]),
                        country=country_text,
                        time_collection_years=years_text,
                    ),
                    "query_topics": _format_list_value([topic]),
                    "query_countries": country_text,
                    "query_time_collection_years": years_qrels_text,
                    "query_time_display": years_text,
                }
            )
        return queries

    if variant == "V3_TITLE_ONLY":
        if not titles:
            return []
        return [
            {
                "query_text": TITLE_QUERY_TEMPLATE.format(title=title),
                "query_topics": "",
                "query_countries": "",
                "query_time_collection_years": "",
                "query_time_display": "",
            }
            for title in titles
        ]

    return []


def generate_queries(config_path: str) -> pd.DataFrame:
    cfg = load_config(config_path)
    output_dir = Path(cfg.get("output_dir", "."))
    output_dir.mkdir(parents=True, exist_ok=True)
    df = load_metadata(cfg["input_path"], cfg["input_format"])
    source_row_limit = int(cfg.get("source_row_limit", 0) or 0)
    if source_row_limit > 0:
        df = df.head(source_row_limit)

    variants = cfg.get("query_variants", list(VARIANTS.keys()))
    time_format = str(cfg.get("time_format", "years")).strip().lower()
    results = []
    seen = set()

    for source_index, row in df.iterrows():
        for variant in variants:
            if variant not in VARIANTS:
                continue
            for query_info in _build_queries_for_row(row, variant, time_format):
                query = str(query_info["query_text"])
                query = _normalize_whitespace(query)
                if not query:
                    continue
                if _contains_identifiers(query, row):
                    continue
                norm = _normalize_query(query)
                key = (variant, norm)
                if key in seen:
                    continue
                seen.add(key)
                results.append(
                    {
                        "query_text": query,
                        "query_variant": variant,
                        "query_topics": query_info["query_topics"],
                        "query_countries": query_info["query_countries"],
                        "query_time_collection_years": query_info["query_time_collection_years"],
                        "query_time_display": query_info["query_time_display"],
                        "source_dataset_id": str(row.get("id", "")),
                        "source_title": str(row.get("title", "")),
                        "source_doi": str(row.get("doi", "")),
                        "source_portal_url": str(row.get("portal_url", "")),
                        "source_row": int(source_index) + 2,
                    }
                )

    out = pd.DataFrame(results)
    if out.empty:
        out.to_csv(output_dir / "queries.csv", index=False)
        return out

    sample_per_variant = int(cfg.get("sample_per_variant", 0) or 0)
    random_seed = int(cfg.get("random_seed", 42))

    sampled_frames = []
    for variant, group in out.groupby("query_variant", sort=False):
        if sample_per_variant > 0:
            n = min(sample_per_variant, len(group))
            sampled = group.sample(n=n, random_state=random_seed)
        else:
            sampled = group
        sampled_frames.append(sampled)

    sampled_out = pd.concat(sampled_frames, ignore_index=True)
    sampled_out = sampled_out.reset_index(drop=True)
    sampled_out.insert(0, "query_id", range(1, len(sampled_out) + 1))

    sampled_out.to_csv(output_dir / "queries.csv", index=False)
    return sampled_out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, help="Path to config.yaml")
    args = parser.parse_args()
    generate_queries(args.config)


if __name__ == "__main__":
    main()
