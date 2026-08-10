import argparse
from pathlib import Path

import pandas as pd

OUTPUT_CSV_SEP = ";"


def read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path, sep=None, engine="python")


def first_value(group: pd.DataFrame, column: str) -> str:
    if column not in group.columns or group.empty:
        return ""
    value = group.iloc[0].get(column, "")
    return "" if pd.isna(value) else str(value)


def best_query_rows(provider: str, output_dir: Path) -> pd.DataFrame:
    metrics = read_csv(output_dir / "metrics_per_query.csv")
    outputs = read_csv(output_dir / "per_query_results.csv")
    queries = read_csv(output_dir / "queries.csv")

    query_text_by_id = {
        int(row.query_id): str(row.query_text)
        for row in queries.itertuples(index=False)
    }

    output_groups = {
        (int(row.query_id), str(row.mode), str(row.model)): group.sort_values("rank")
        for (query_id, mode, model), group in outputs.groupby(["query_id", "mode", "model"], sort=False)
        for row in [group.iloc[0]]
    }

    rows = []
    for metric in metrics.itertuples(index=False):
        query_id = int(metric.query_id)
        mode = str(metric.mode)
        model = str(metric.model)
        group = output_groups.get((query_id, mode, model), pd.DataFrame())

        strict_gesis_group = (
            group[group.get("is_strict_gesis_relevant_dataset", pd.Series(dtype=str)).astype(str) == "1"]
            if not group.empty
            else pd.DataFrame()
        )
        gesis_group = (
            group[group.get("is_gesis_relevant_dataset", pd.Series(dtype=str)).astype(str) == "1"]
            if not group.empty
            else pd.DataFrame()
        )
        strict_source_group = (
            group[group.get("is_strict_source_dataset", pd.Series(dtype=str)).astype(str) == "1"]
            if not group.empty
            else pd.DataFrame()
        )
        source_group = (
            group[group.get("is_source_dataset", pd.Series(dtype=str)).astype(str) == "1"]
            if not group.empty
            else pd.DataFrame()
        )
        chosen = strict_source_group
        if chosen.empty:
            chosen = strict_gesis_group
        if chosen.empty:
            chosen = source_group
        if chosen.empty:
            chosen = gesis_group
        if chosen.empty:
            chosen = group.head(1)

        rows.append(
            {
                "provider": provider,
                "query_id": query_id,
                "query_text": query_text_by_id.get(query_id, ""),
                "mode": mode,
                "model": model,
                "hit_at_k": getattr(metric, "hit_at_k", 0),
                "strict_hit_at_k": getattr(metric, "strict_hit_at_k", 0),
                "title_match_hit_at_k": getattr(metric, "title_match_hit_at_k", 0),
                "gesis_relevant_hit_at_k": getattr(metric, "gesis_relevant_hit_at_k", 0),
                "strict_gesis_relevant_hit_at_k": getattr(metric, "strict_gesis_relevant_hit_at_k", 0),
                "source_hit_at_k": getattr(metric, "source_hit_at_k", 0),
                "strict_source_hit_at_k": getattr(metric, "strict_source_hit_at_k", 0),
                "mrr": getattr(metric, "mrr", 0),
                "strict_mrr": getattr(metric, "strict_mrr", 0),
                "selected_rank": first_value(chosen, "rank"),
                "selected_returned_title": first_value(chosen, "returned_title"),
                "selected_returned_url_or_doi": first_value(chosen, "returned_url_or_doi"),
                "selected_matched_dataset_id": first_value(chosen, "matched_dataset_id"),
                "selected_match_method": first_value(chosen, "match_method"),
                "selected_is_relevant": first_value(chosen, "is_relevant"),
                "selected_is_strict_relevant": first_value(chosen, "is_strict_relevant"),
                "selected_is_gesis_relevant_dataset": first_value(chosen, "is_gesis_relevant_dataset"),
                "selected_is_strict_gesis_relevant_dataset": first_value(chosen, "is_strict_gesis_relevant_dataset"),
                "selected_is_source_dataset": first_value(chosen, "is_source_dataset"),
                "selected_is_strict_source_dataset": first_value(chosen, "is_strict_source_dataset"),
                "selected_link_valid": first_value(chosen, "link_valid"),
            }
        )

    return pd.DataFrame(rows)


def compare(openai_dir: Path, openwebui_dir: Path, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    openai = best_query_rows("openai", openai_dir)
    openwebui = best_query_rows("openwebui", openwebui_dir)
    combined = pd.concat([openai, openwebui], ignore_index=True)

    keys = ["query_id", "mode"]
    openai_keyed = openai.set_index(keys)
    openwebui_keyed = openwebui.set_index(keys)
    rows = []

    all_keys = sorted(set(openai_keyed.index) | set(openwebui_keyed.index))
    for key in all_keys:
        left = openai_keyed.loc[key] if key in openai_keyed.index else pd.Series(dtype=object)
        right = openwebui_keyed.loc[key] if key in openwebui_keyed.index else pd.Series(dtype=object)
        if isinstance(left, pd.DataFrame):
            left = left.iloc[0]
        if isinstance(right, pd.DataFrame):
            right = right.iloc[0]

        openai_strict = int(float(left.get("strict_gesis_relevant_hit_at_k", 0) or 0))
        openwebui_strict = int(float(right.get("strict_gesis_relevant_hit_at_k", 0) or 0))
        if openai_strict and not openwebui_strict:
            verdict = "openai_strict_gesis_only"
        elif openwebui_strict and not openai_strict:
            verdict = "openwebui_strict_gesis_only"
        elif openai_strict and openwebui_strict:
            verdict = "both_strict_gesis"
        else:
            verdict = "neither_strict_gesis"

        rows.append(
            {
                "query_id": key[0],
                "mode": key[1],
                "query_text": left.get("query_text") or right.get("query_text", ""),
                "verdict": verdict,
                "openai_model": left.get("model", ""),
                "openai_hit_at_k": left.get("hit_at_k", ""),
                "openai_strict_hit_at_k": left.get("strict_hit_at_k", ""),
                "openai_title_match_hit_at_k": left.get("title_match_hit_at_k", ""),
                "openai_gesis_relevant_hit_at_k": left.get("gesis_relevant_hit_at_k", ""),
                "openai_strict_gesis_relevant_hit_at_k": left.get("strict_gesis_relevant_hit_at_k", ""),
                "openai_source_hit_at_k": left.get("source_hit_at_k", ""),
                "openai_strict_source_hit_at_k": left.get("strict_source_hit_at_k", ""),
                "openai_selected_title": left.get("selected_returned_title", ""),
                "openai_selected_url_or_doi": left.get("selected_returned_url_or_doi", ""),
                "openai_selected_matched_dataset_id": left.get("selected_matched_dataset_id", ""),
                "openai_selected_match_method": left.get("selected_match_method", ""),
                "openwebui_model": right.get("model", ""),
                "openwebui_hit_at_k": right.get("hit_at_k", ""),
                "openwebui_strict_hit_at_k": right.get("strict_hit_at_k", ""),
                "openwebui_title_match_hit_at_k": right.get("title_match_hit_at_k", ""),
                "openwebui_gesis_relevant_hit_at_k": right.get("gesis_relevant_hit_at_k", ""),
                "openwebui_strict_gesis_relevant_hit_at_k": right.get("strict_gesis_relevant_hit_at_k", ""),
                "openwebui_source_hit_at_k": right.get("source_hit_at_k", ""),
                "openwebui_strict_source_hit_at_k": right.get("strict_source_hit_at_k", ""),
                "openwebui_selected_title": right.get("selected_returned_title", ""),
                "openwebui_selected_url_or_doi": right.get("selected_returned_url_or_doi", ""),
                "openwebui_selected_matched_dataset_id": right.get("selected_matched_dataset_id", ""),
                "openwebui_selected_match_method": right.get("selected_match_method", ""),
            }
        )

    comparison = pd.DataFrame(rows)
    combined.to_csv(out_dir / "provider_outputs_query_level.csv", index=False, sep=OUTPUT_CSV_SEP)
    comparison.to_csv(out_dir / "provider_differences.csv", index=False, sep=OUTPUT_CSV_SEP)

    summary = (
        comparison.groupby(["mode", "verdict"], sort=False)
        .size()
        .reset_index(name="count")
    )
    summary.to_csv(out_dir / "provider_difference_summary.csv", index=False, sep=OUTPUT_CSV_SEP)

    print(f"Wrote {out_dir / 'provider_outputs_query_level.csv'}")
    print(f"Wrote {out_dir / 'provider_differences.csv'}")
    print(f"Wrote {out_dir / 'provider_difference_summary.csv'}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--openai-dir", required=True)
    parser.add_argument("--openwebui-dir", required=True)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()

    compare(Path(args.openai_dir), Path(args.openwebui_dir), Path(args.out_dir))


if __name__ == "__main__":
    main()
