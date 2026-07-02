import argparse
import ast
import json
import re
from pathlib import Path

import pandas as pd
import yaml

from .load_metadata import load_metadata
from .config_paths import apply_variant_override, resolve_output_dir
from .prompts import build_messages, format_messages

RE_DOI = re.compile(r"10\.\d{4,9}/\S+", re.IGNORECASE)
OUTPUT_CSV_SEP = ";"

QUERY_TEMPLATE = "Can you find datasets about {topic} in {country} during the {time_collection_years}?"
POPULATION_UNIT_QUERY_TEMPLATE = (
    "Can you find datasets about {topic} in {country} during the {time_collection_years}, "
    "where the study population is {universe} and the unit of analysis is {analysis_unit}?"
)
POPULATION_QUERY_TEMPLATE = (
    "Can you find datasets about {topic} in {country} during the {time_collection_years}, "
    "where the study population is {universe}?"
)
TITLE_QUERY_TEMPLATE = "Can you find the dataset titled {title}?"

VARIANTS = {
    "V1_TOPIC_COUNTRY_TIME_ALL_TOPICS": "all_topics",
    "V2_TOPIC_COUNTRY_TIME_SINGLE_TOPIC": "single_topic",
    "V3_TITLE_ONLY": "title",
    "V4_TOPIC_COUNTRY_TIME_UNIVERSE_ANALYSIS_UNIT_ALL_TOPICS": "all_topics_population_unit",
    "V5_TOPIC_COUNTRY_TIME_UNIVERSE_ALL_TOPICS": "all_topics_population",
}

MISSING_METADATA_LABELS = {
    "n/a",
    "no specific information",
    "not applicable",
    "not specified",
    "unknown",
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


def _format_natural_list(values: list[str]) -> str:
    cleaned = [_normalize_whitespace(value) for value in values if _normalize_whitespace(value)]
    if not cleaned:
        return ""
    if len(cleaned) == 1:
        return cleaned[0]
    if len(cleaned) == 2:
        return f"{cleaned[0]} and {cleaned[1]}"
    return f"{', '.join(cleaned[:-1])}, and {cleaned[-1]}"


def _meaningful_values(values: list[str]) -> list[str]:
    return [
        value
        for value in values
        if _normalize_whitespace(value).casefold() not in MISSING_METADATA_LABELS
    ]


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
    universes = _meaningful_values(_parse_list_value(row.get("universe", "")))
    analysis_units = _meaningful_values(_parse_list_value(row.get("analysis_unit", "")))

    if variant == "V1_TOPIC_COUNTRY_TIME_ALL_TOPICS":
        if not topics or not countries or not years:
            return []
        country_text = _format_natural_list(countries)
        country_qrels_text = _format_list_value(countries)
        years_text = _format_time_value(years, time_format)
        years_qrels_text = _format_list_value(years)
        topic_text = _format_natural_list(topics)
        topic_qrels_text = _format_list_value(topics)
        return [
            {
                "query_text": QUERY_TEMPLATE.format(
                    topic=topic_text,
                    country=country_text,
                    time_collection_years=years_text,
                ),
                "query_topics": topic_qrels_text,
                "query_countries": country_qrels_text,
                "query_time_collection_years": years_qrels_text,
                "query_time_display": years_text,
                "query_universe": "",
                "query_analysis_units": "",
            }
        ]

    if variant == "V2_TOPIC_COUNTRY_TIME_SINGLE_TOPIC":
        if not topics or not countries or not years:
            return []
        country_text = _format_natural_list(countries)
        country_qrels_text = _format_list_value(countries)
        years_text = _format_time_value(years, time_format)
        years_qrels_text = _format_list_value(years)
        queries = []
        for topic in topics:
            topic_qrels_text = _format_list_value([topic])
            queries.append(
                {
                    "query_text": QUERY_TEMPLATE.format(
                        topic=_format_natural_list([topic]),
                        country=country_text,
                        time_collection_years=years_text,
                    ),
                    "query_topics": topic_qrels_text,
                    "query_countries": country_qrels_text,
                    "query_time_collection_years": years_qrels_text,
                    "query_time_display": years_text,
                    "query_universe": "",
                    "query_analysis_units": "",
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
                "query_universe": "",
                "query_analysis_units": "",
            }
            for title in titles
        ]

    if variant == "V4_TOPIC_COUNTRY_TIME_UNIVERSE_ANALYSIS_UNIT_ALL_TOPICS":
        if not topics or not countries or not years or not universes or not analysis_units:
            return []
        country_text = _format_natural_list(countries)
        years_text = _format_time_value(years, time_format)
        universe_text = _format_natural_list(universes)
        analysis_unit_text = _format_natural_list(analysis_units)
        return [
            {
                "query_text": POPULATION_UNIT_QUERY_TEMPLATE.format(
                    topic=_format_natural_list(topics),
                    country=country_text,
                    time_collection_years=years_text,
                    universe=universe_text,
                    analysis_unit=analysis_unit_text,
                ),
                "query_topics": _format_list_value(topics),
                "query_countries": _format_list_value(countries),
                "query_time_collection_years": _format_list_value(years),
                "query_time_display": years_text,
                "query_universe": _format_list_value(universes),
                "query_analysis_units": _format_list_value(analysis_units),
            }
        ]

    if variant == "V5_TOPIC_COUNTRY_TIME_UNIVERSE_ALL_TOPICS":
        if not topics or not countries or not years or not universes:
            return []
        years_text = _format_time_value(years, time_format)
        return [
            {
                "query_text": POPULATION_QUERY_TEMPLATE.format(
                    topic=_format_natural_list(topics),
                    country=_format_natural_list(countries),
                    time_collection_years=years_text,
                    universe=_format_natural_list(universes),
                ),
                "query_topics": _format_list_value(topics),
                "query_countries": _format_list_value(countries),
                "query_time_collection_years": _format_list_value(years),
                "query_time_display": years_text,
                "query_universe": _format_list_value(universes),
                "query_analysis_units": "",
            }
        ]

    return []


def generate_queries(config_path: str, variant: str | None = None) -> pd.DataFrame:
    cfg = apply_variant_override(load_config(config_path), variant)
    output_dir = resolve_output_dir(cfg)
    output_dir.mkdir(parents=True, exist_ok=True)
    df = load_metadata(cfg["input_path"], cfg["input_format"])
    source_row_limit = int(cfg.get("source_row_limit", 0) or 0)
    if source_row_limit > 0:
        df = df.head(source_row_limit)

    variants = cfg.get("query_variants", list(VARIANTS.keys()))
    time_format = str(cfg.get("time_format", "years")).strip().lower()
    top_k = int(cfg.get("top_k_return", 10))
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
                        "full_prompt_no_web": format_messages(
                            build_messages(query, top_k, "NO_WEB")
                        ),
                        "full_prompt_web_search": format_messages(
                            build_messages(query, top_k, "WEB_SEARCH")
                        ),
                        "query_variant": variant,
                        "query_topics": query_info["query_topics"],
                        "query_countries": query_info["query_countries"],
                        "query_time_collection_years": query_info["query_time_collection_years"],
                        "query_time_display": query_info["query_time_display"],
                        "query_universe": query_info["query_universe"],
                        "query_analysis_units": query_info["query_analysis_units"],
                        "source_dataset_id": str(row.get("id", "")),
                        "source_title": str(row.get("title", "")),
                        "source_doi": str(row.get("doi", "")),
                        "source_portal_url": str(row.get("portal_url", "")),
                        "source_row": int(source_index) + 2,
                    }
                )

    out = pd.DataFrame(results)
    if out.empty:
        out.to_csv(output_dir / "queries.csv", index=False, sep=OUTPUT_CSV_SEP)
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

    sampled_out.to_csv(output_dir / "queries.csv", index=False, sep=OUTPUT_CSV_SEP)
    return sampled_out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, help="Path to config.yaml")
    parser.add_argument("-V", "--variant", help="Override query variant (V1, V2, V3, V4, or V5)")
    args = parser.parse_args()
    generate_queries(args.config, args.variant)


if __name__ == "__main__":
    main()
