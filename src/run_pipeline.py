"""Resolve experiment profiles and run the existing pipeline stages."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone
from uuid import uuid4

import yaml

from src.config_paths import resolve_variant

ROOT = Path(__file__).resolve().parents[1]
STAGES = ("generate_queries", "run_llm", "match_and_eval", "audit_results")


def read_yaml(path):
    with Path(path).open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def resolve_config(catalog, args):
    provider = catalog["providers"][args.provider]
    dataset = catalog["datasets"][args.sample]
    template = dict(catalog["templates"][args.template])
    variant = resolve_variant(args.variant)
    allowed = template.pop("variants", None)
    if allowed and variant not in [resolve_variant(value) for value in allowed]:
        raise ValueError(f"Template {args.template} is not compatible with {args.variant}")
    cfg = {**catalog["defaults"], **dataset, **provider, **template}
    model = args.model or cfg.pop("model")
    cfg.pop("model", None)
    cfg["query_variants"] = [variant]
    cfg["modes"] = [args.mode]
    cfg["models_web"] = [model] if args.mode == "WEB_SEARCH" else []
    cfg["models_no_web"] = [model] if args.mode == "NO_WEB" else []
    if args.input_path:
        cfg["input_path"] = args.input_path
        # A custom corpus must not reuse another sample's abstract cache.
        cfg.pop("abstract_query_cache_path", None)
    if args.qrels_input_path:
        cfg["qrels_input_path"] = args.qrels_input_path
    if args.limit is not None:
        cfg["source_row_limit"] = args.limit
    for key in ("input_path", "qrels_input_path"):
        if not cfg.get(key):
            raise ValueError(f"Missing required setting: {key}; set it in the catalog or pass --{key.replace('_', '-')}")
    for key in ("input_path", "qrels_input_path", "abstract_query_cache_path"):
        if cfg.get(key):
            cfg[key] = str((ROOT / cfg[key]).resolve())
    return cfg


def fingerprint(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return {"path": str(path), "sha256": digest.hexdigest()}


def parser():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", default="experiment.yaml")
    ap.add_argument("--provider", choices=("openai", "gemini", "openwebui"))
    ap.add_argument("--model")
    ap.add_argument("--sample", default="random100")
    ap.add_argument("-V", "--variant")
    ap.add_argument("--template", default="default")
    ap.add_argument("--mode", choices=("WEB_SEARCH", "NO_WEB"), default="WEB_SEARCH")
    ap.add_argument("--input-path")
    ap.add_argument("--qrels-input-path")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--output-root")
    ap.add_argument("--run-dir", help="Resume an existing run using its saved configuration")
    ap.add_argument("--stages", nargs="+", choices=STAGES, default=list(STAGES))
    ap.add_argument("--dry-run", action="store_true", help="Print settings without writing files or calling APIs")
    return ap


def main():
    ap = parser()
    args = ap.parse_args()
    if args.limit is not None and args.limit < 0:
        ap.error("--limit must be zero (all rows) or positive")
    if args.run_dir:
        if args.provider or args.variant or args.model or args.input_path or args.qrels_input_path or args.limit is not None or args.template != "default" or args.sample != "random100" or args.mode != "WEB_SEARCH" or args.output_root:
            ap.error("Resume uses saved settings; do not pass experiment overrides with --run-dir")
        run_dir = (ROOT / args.run_dir).resolve()
        config_path = run_dir / "resolved_config.yaml"
        cfg = read_yaml(config_path)
        if Path(cfg["output_dir"]).resolve() != run_dir:
            ap.error("Saved output directory differs from --run-dir")
    else:
        if not args.provider or not args.variant:
            ap.error("A new experiment requires --provider and --variant")
        if args.stages[0] != "generate_queries":
            ap.error("A new experiment starts with generate_queries; use --run-dir for later stages")
        catalog = read_yaml(ROOT / args.config)
        try:
            cfg = resolve_config(catalog, args)
        except (KeyError, ValueError) as exc:
            ap.error(str(exc))
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        name = f"{stamp}_{args.sample}_{args.provider}_{args.variant}_{args.template}_{uuid4().hex[:8]}"
        run_dir = (ROOT / (args.output_root or catalog["output_root"]) / name).resolve()
        cfg["output_dir"] = str(run_dir)
        config_path = run_dir / "resolved_config.yaml"
    print(yaml.safe_dump(cfg, sort_keys=False), flush=True)
    print(f"Stages: {', '.join(args.stages)}", flush=True)
    if args.dry_run:
        return
    if not args.run_dir:
        try:
            inputs = {key: fingerprint(cfg[key]) for key in ("input_path", "qrels_input_path")}
        except OSError as exc:
            ap.error(f"Cannot read experiment input: {exc}")
        run_dir.mkdir(parents=True, exist_ok=False)
        config_path.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
        manifest = {"created_at": datetime.now(timezone.utc).isoformat(), "selection": vars(args), "inputs": inputs}
        (run_dir / "experiment.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    for stage in args.stages:
        print(f"Running {stage} in {run_dir}", flush=True)
        result = subprocess.run([sys.executable, "-m", f"src.{stage}", "--config", str(config_path)], cwd=ROOT)
        event = {"stage": stage, "finished_at": datetime.now(timezone.utc).isoformat(), "exit_code": result.returncode}
        with (run_dir / "stages.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event) + "\n")
        if result.returncode:
            raise SystemExit(result.returncode)
    print(f"Results: {run_dir}")


if __name__ == "__main__":
    main()
