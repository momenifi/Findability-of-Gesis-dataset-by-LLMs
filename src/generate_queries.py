import argparse
import re
from pathlib import Path

import pandas as pd
import yaml

from .load_metadata import load_metadata

RE_DOI = re.compile(r"10\.\d{4,9}/\S+", re.IGNORECASE)

TEMPLATES = {
    "V1_TOPIC": "{topic}",
    "V2_TOPIC_METHOD": "{topic} {methodology}",
    "V3_TOPIC_COUNTRY": "{topic} {country}",
    "V4_TOPIC_UNIVERSE": "{topic} {universe}",
    "V5_TOPIC_TITLE": "{topic} {title}",
}


def _normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _normalize_query(text: str) -> str:
    return _normalize_whitespace(text).lower()


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


def generate_queries(config_path: str) -> pd.DataFrame:
    cfg = load_config(config_path)
    df = load_metadata(cfg["input_path"], cfg["input_format"])

    variants = cfg.get("query_variants", list(TEMPLATES.keys()))
    results = []
    seen = set()

    for _, row in df.iterrows():
        for variant in variants:
            template = TEMPLATES.get(variant)
            if not template:
                continue
            query = template.format(
                topic=row.get("topic", ""),
                methodology=row.get("methodology", ""),
                country=row.get("country", ""),
                universe=row.get("universe", ""),
                title=row.get("title", ""),
            )
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
            results.append({"query_text": query, "query_variant": variant})

    out = pd.DataFrame(results)
    if out.empty:
        out.to_csv("queries.csv", index=False)
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

    sampled_out.to_csv("queries.csv", index=False)
    return sampled_out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, help="Path to config.yaml")
    args = parser.parse_args()
    generate_queries(args.config)


if __name__ == "__main__":
    main()
