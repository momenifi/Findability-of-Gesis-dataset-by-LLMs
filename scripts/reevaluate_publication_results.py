"""Reevaluate the selected saved publication runs locally, without API calls."""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil

import yaml

from scripts.build_publication_report import DEFAULT_RUN, ROOT, VARIANTS, build, interpretation, source_root
from src.audit_results import audit
from src.match_and_eval import match_and_eval
from src.load_metadata import load_metadata


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def finish_report(backup):
    status = json.loads((backup / "status.json").read_text(encoding="utf-8"))
    if len(status["runs"]) != 16 or not all(run["queries_and_responses_unchanged"] for run in status["runs"]):
        raise ValueError("All 16 evaluations must finish before publishing")
    publication = ROOT / "reports/current_results"
    rows = build(DEFAULT_RUN, publication)
    (publication / "INTERPRETATION.md").write_text(interpretation(rows), encoding="utf-8")
    (publication.parent / "README.md").write_bytes((ROOT / "scripts/report_templates/reports_README.md").read_bytes())
    status["completed"] = True
    (backup / "status.json").write_text(json.dumps(status, indent=2), encoding="utf-8")
    print(f"Reevaluated 16 conditions. Backup: {backup}. No API calls.", flush=True)


def main():
    backup = ROOT / "output/archive/evaluation_refresh" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    backup.mkdir(parents=True)
    publication = ROOT / "reports/current_results"
    shutil.copytree(publication, backup / "publication_before")
    corpus = ROOT / "all_research_data_full_metadata.csv"
    metadata = load_metadata(str(corpus), "csv")
    status = {"corpus_sha256": digest(corpus), "runs": [], "completed": False,
              "qrels": "Existing relevance sets preserved; matching-only correction"}
    for sample in ("random100", "top10"):
        for provider in ("OpenAI", "Gemini"):
            root = source_root(sample, provider)
            for variant, folder in VARIANTS.items():
                directory = root / folder
                snapshot = backup / sample / provider / folder
                snapshot.mkdir(parents=True)
                for path in directory.glob("*.csv"):
                    if path.name not in ("queries.csv", "llm_results.csv"):
                        shutil.copy2(path, snapshot / path.name)
                protected = {name: digest(directory / name) for name in ("queries.csv", "llm_results.csv", "qrels.csv")}
                config_source = directory / "config.yaml"
                cfg = yaml.safe_load(config_source.read_text(encoding="utf-8"))
                cfg.update(output_dir=str(directory), qrels_input_path=str(corpus),
                           input_path=str(ROOT / ("random_100_datasets_full_metadata.csv" if sample == "random100"
                                                 else "top 10/requested_10_datasets_full_metadata.csv")))
                cfg.pop("output_dir_by_variant", None)
                config = snapshot / "local_config.yaml"
                config.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
                print(f"Evaluating {sample} / {provider} / {variant}", flush=True)
                match_and_eval(str(config), metadata=metadata, reuse_qrels=True)
                audit(str(config))
                assert all(digest(directory / name) == expected for name, expected in protected.items())
                status["runs"].append({"sample": sample, "provider": provider, "variant": variant,
                                       "queries_and_responses_unchanged": True})
                (backup / "status.json").write_text(json.dumps(status, indent=2), encoding="utf-8")
    finish_report(backup)


if __name__ == "__main__":
    main()
