import argparse
import re
from pathlib import Path

import pandas as pd
import yaml

from .config_paths import apply_variant_override, resolve_output_dir
from .load_metadata import load_metadata
from .match_and_eval import _extract_doi, _normalize_doi, _normalize_dois, _normalize_url

OUTPUT_CSV_SEP = ";"
RE_URL = re.compile(r"https?://[^\s\"'<>]+", re.IGNORECASE)


def load_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _iter_cell_dois(value: object) -> list[str]:
    text = "" if pd.isna(value) else str(value)
    dois = []
    for match in re.finditer(r"10\.\d{4,9}/[^\s\"'<>),;\]]+", text, flags=re.IGNORECASE):
        doi = _normalize_doi(match.group(0))
        if doi and doi not in dois:
            dois.append(doi)
    return dois


def _extract_urls(value: object) -> list[str]:
    text = "" if pd.isna(value) else str(value)
    return [_normalize_url(match.group(0)) for match in RE_URL.finditer(text)]


def build_known_link_index(metadata: pd.DataFrame) -> tuple[set[str], set[str]]:
    known_dois: set[str] = set()
    known_urls: set[str] = set()

    doi_rich_columns = [
        "id",
        "doi",
        "handle",
        "portal_url",
        "link",
        "current_version",
        "citation_string",
        "citation_string_en",
        "version_table",
        "version_table_en",
        "links_research_data",
        "links_dataset",
        "links_codebook",
        "links_questionnaire",
    ]

    for _, row in metadata.iterrows():
        dataset_id = str(row.get("id", "") or "").strip()
        if dataset_id.startswith("SDN-"):
            doi = _normalize_doi(dataset_id.replace("SDN-", "", 1))
            if doi:
                known_dois.add(doi)

        for col in doi_rich_columns:
            if col not in metadata.columns:
                continue
            value = row.get(col, "")
            known_dois.update(_iter_cell_dois(value))
            known_urls.update(url for url in _extract_urls(value) if url)

    for doi in list(known_dois):
        known_urls.add(_normalize_url(f"https://doi.org/{doi}"))

    return known_dois, known_urls


def add_query_source_links(queries: pd.DataFrame, known_dois: set[str], known_urls: set[str]) -> None:
    for _, row in queries.iterrows():
        for doi in _normalize_dois(str(row.get("source_doi", "") or "")):
            known_dois.add(doi)
            known_urls.add(_normalize_url(f"https://doi.org/{doi}"))

        portal = _normalize_url(str(row.get("source_portal_url", "") or ""))
        if portal:
            known_urls.add(portal)


def classify_link(row: pd.Series, known_dois: set[str], known_urls: set[str]) -> dict:
    raw = str(row.get("returned_url_or_doi", "") or "").strip()
    normalized_url = _normalize_url(raw)
    returned_doi = _extract_doi(raw)
    link_valid = str(row.get("link_valid", "")).lower() in {"true", "1"}

    doi_known_anywhere = bool(returned_doi and returned_doi in known_dois)
    url_known_anywhere = bool(normalized_url and normalized_url in known_urls)

    if link_valid or doi_known_anywhere or url_known_anywhere:
        audit_class = "known_in_metadata"
        suspect = 0
    elif not raw:
        audit_class = "empty_link"
        suspect = 0
    elif re.search(r"search\.gesis\.org/research_data/?$", normalized_url):
        audit_class = "generic_gesis_search_url"
        suspect = 0
    elif returned_doi:
        audit_class = "doi_not_found_in_metadata"
        suspect = 1
    elif re.search(r"gesis\.org|dbk\.gesis\.org", normalized_url):
        audit_class = "gesis_url_not_found_in_metadata"
        suspect = 1
    elif re.match(r"^https?://", normalized_url):
        audit_class = "external_or_other_url"
        suspect = 0
    else:
        audit_class = "malformed_or_text"
        suspect = 1

    return {
        "returned_doi": returned_doi,
        "normalized_returned_url": normalized_url,
        "doi_known_anywhere_in_metadata": int(doi_known_anywhere),
        "url_known_anywhere_in_metadata": int(url_known_anywhere),
        "link_audit_class": audit_class,
        "is_suspect_hallucinated_link": suspect,
    }


def audit_links(config_path: str, variant: str | None = None) -> None:
    cfg = apply_variant_override(load_config(config_path), variant)
    output_dir = resolve_output_dir(cfg)
    per_query_path = output_dir / "per_query_results.csv"

    if not per_query_path.exists():
        raise FileNotFoundError(f"{per_query_path} not found. Run match_and_eval first.")

    metadata_input = cfg.get("qrels_input_path") or cfg.get("input_path")
    metadata_format = cfg.get("qrels_input_format") or cfg.get("input_format", "csv")
    metadata = load_metadata(metadata_input, metadata_format)
    known_dois, known_urls = build_known_link_index(metadata)
    queries_path = output_dir / "queries.csv"
    if queries_path.exists():
        queries = pd.read_csv(queries_path, sep=None, engine="python")
        add_query_source_links(queries, known_dois, known_urls)

    results = pd.read_csv(per_query_path, sep=None, engine="python")
    audit_cols = results.apply(lambda row: classify_link(row, known_dois, known_urls), axis=1)
    audit_df = pd.concat([results, pd.DataFrame(list(audit_cols))], axis=1)
    if "variant" not in audit_df.columns and "query_variant" in audit_df.columns:
        audit_df["variant"] = audit_df["query_variant"]

    summary = (
        audit_df.groupby(["variant", "mode", "model", "link_audit_class"], dropna=False)
        .size()
        .reset_index(name="item_rows")
        .sort_values(["variant", "mode", "model", "link_audit_class"])
    )
    suspect_summary = (
        audit_df.groupby(["variant", "mode", "model"], dropna=False)
        .agg(
            returned_item_rows=("query_id", "count"),
            suspect_hallucinated_link_rows=("is_suspect_hallucinated_link", "sum"),
        )
        .reset_index()
    )
    suspect_summary["suspect_hallucinated_link_rate"] = (
        suspect_summary["suspect_hallucinated_link_rows"]
        / suspect_summary["returned_item_rows"].replace(0, pd.NA)
    ).fillna(0).round(3)

    output_dir.mkdir(parents=True, exist_ok=True)
    audit_path = output_dir / "link_audit.csv"
    summary_path = output_dir / "link_audit_summary.csv"
    suspect_summary_path = output_dir / "link_audit_suspect_summary.csv"
    audit_df.to_csv(audit_path, index=False, sep=OUTPUT_CSV_SEP)
    summary.to_csv(summary_path, index=False, sep=OUTPUT_CSV_SEP)
    suspect_summary.to_csv(suspect_summary_path, index=False, sep=OUTPUT_CSV_SEP)

    print(f"Wrote {audit_path}")
    print(f"Wrote {summary_path}")
    print(f"Wrote {suspect_summary_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit returned DOI/URL validity against metadata.")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("-V", "--variant", default=None)
    args = parser.parse_args()
    audit_links(args.config, args.variant)


if __name__ == "__main__":
    main()
