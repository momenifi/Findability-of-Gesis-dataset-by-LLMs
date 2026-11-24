"""Repeat saved random-100 and top-10 OpenAI queries with required search."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone
from uuid import uuid4

import pandas as pd
import yaml

from src.prompts import build_messages, format_messages


ROOT = Path(__file__).resolve().parents[1]
SAMPLES = {
    "random100": "output/current_results_sources/openai/random100",
    "top10": "output/current_results_sources/openai/top10",
}
VARIANTS = ("v1_all_topics", "v2_single_topic", "v3_title_only", "v6_all_topics_abstract_natural_language")


def prepare(destination):
    prepared = []
    # Validate every source before creating the new experiment.
    for sample, source in SAMPLES.items():
        for variant in VARIANTS:
            cfg = yaml.safe_load((ROOT / source / variant / "config.yaml").read_text(encoding="utf-8"))
            path = ROOT / source / variant / "queries.csv"
            queries = pd.read_csv(path, sep=";", keep_default_na=False)
            if queries.empty or queries.query_id.duplicated().any():
                raise ValueError(f"Empty or duplicate queries: {path}")
            for row in queries.itertuples(index=False):
                actual = format_messages(build_messages(row.query_text, cfg["top_k_return"], "WEB_SEARCH", False))
                if getattr(row, "full_prompt_web_search", actual) != actual:
                    raise ValueError(f"Saved prompt differs from current messages: {path}, query {row.query_id}")
            prepared.append((sample, variant, cfg, path, queries))
    destination.mkdir(parents=True, exist_ok=False)
    runs = []
    for sample, variant, cfg, source, queries in prepared:
        directory = destination / sample / variant
        directory.mkdir(parents=True)
        settings = {**cfg, "provider": "openai", "api_base_url": "https://api.openai.com/v1",
                    "api_key_env": "OPENAI_API_KEY", "output_dir": str(directory),
                    "query_variants": list(queries.query_variant.unique()),
                    "modes": ["WEB_SEARCH"], "models_no_web": [],
                    "openai_web_search_tool_choice": "required",
                    "include_top_k_limit_in_prompt": False, "max_returned_items_to_save": 0}
        settings.pop("output_dir_by_variant", None)
        (directory / "config.yaml").write_text(yaml.safe_dump(settings, sort_keys=False), encoding="utf-8")
        # Copy bytes exactly; do not regenerate V6 research needs or CSV content.
        content = source.read_bytes()
        (directory / "queries.csv").write_bytes(content)
        runs.append({"sample": sample, "variant": variant, "directory": str(directory.relative_to(destination)),
                     "queries": len(queries), "source": str(source.relative_to(ROOT)),
                     "queries_sha256": hashlib.sha256(content).hexdigest()})
    manifest = {"created_at": datetime.now(timezone.utc).isoformat(), "search_tool_choice": "required",
                "runs": runs, "planned_requests": sum(run["queries"] for run in runs)}
    (destination / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="Make paid API calls, then evaluate and audit")
    parser.add_argument("--run-dir", type=Path, help="Execute an already prepared, unused experiment")
    args = parser.parse_args()
    if args.run_dir:
        directory = args.run_dir.resolve()
        manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    else:
        name = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_" + uuid4().hex[:8]
        directory = ROOT / "output/openai_required_websearch" / name
        manifest = prepare(directory)
    print(f"Results: {directory}\nPlanned requests: {manifest['planned_requests']}", flush=True)
    if not args.execute:
        print("Prepared only; no API calls. Run:", flush=True)
        print(f'python -m scripts.run_openai_required --run-dir "{directory}" --execute')
        return
    if not os.environ.get("OPENAI_API_KEY"):
        parser.error("Set OPENAI_API_KEY in this terminal before execution")
    for run in manifest["runs"]:
        folder = directory / run["directory"]
        if (folder / "llm_results.csv").exists():
            parser.error(f"Refusing to overwrite existing results: {folder}")
    for run in manifest["runs"]:
        for stage in ("run_llm", "match_and_eval", "audit_results"):
            print(f"{run['sample']} / {run['variant']} / {stage}", flush=True)
            subprocess.run([sys.executable, "-m", f"src.{stage}", "--config",
                            str(directory / run["directory"] / "config.yaml")], cwd=ROOT, check=True)


if __name__ == "__main__":
    main()
