"""Local experiment storage and background execution for the research UI."""

import ctypes
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from types import SimpleNamespace
from uuid import uuid4

import pandas as pd
import yaml

from src.run_pipeline import ROOT, STAGES, fingerprint, read_yaml, resolve_config

RUN_ROOT = ROOT / "output" / "experiments"
UPLOAD_ROOT = ROOT / "output" / "web_uploads"
VARIANT_METADATA = {
    "V1": ("topic", "country", "time_collection_years"),
    "V2": ("topic", "country", "time_collection_years"),
    "V3": ("title",),
    "V4": ("topic", "country", "time_collection_years", "universe", "analysis_unit"),
    "V5": ("topic", "country", "time_collection_years", "universe"),
    "V6": ("topic", "country", "time_collection_years", "abstract"),
}
METADATA_SOURCES = {
    "title": "title_en / title",
    "topic": "topic_en / topic",
    "country": "countries_collection_en / countries_collection",
    "time_collection_years": "time_collection_years",
    "universe": "universe_en / universe",
    "analysis_unit": "analysis_unit_en / analysis_unit",
    "abstract": "abstract_en / abstract",
}
TEMPLATE_KEYS = {"V1": "metadata_query_template", "V2": "metadata_query_template",
                 "V3": "title_query_template", "V4": "population_unit_query_template",
                 "V5": "population_query_template", "V6": "abstract_query_template"}


def variant_for_metadata(fields, topic_mode="All topics"):
    chosen = set(fields)
    for variant, required in VARIANT_METADATA.items():
        if variant == "V2":
            continue
        if chosen == set(required):
            return "V2" if variant == "V1" and topic_mode == "Single topic" else variant
    raise ValueError("This metadata combination does not yet have relevance rules. Choose one of the supported presets.")


def compatible_templates(catalog, variant):
    from src.config_paths import resolve_variant
    return [name for name, settings in catalog["templates"].items()
            if name != "default" and variant in [resolve_variant(value).split("_")[0]
                                                for value in settings.get("variants", [])]]


def read_json(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def write_json(path, value):
    path = Path(path)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, indent=2), encoding="utf-8")
    temporary.replace(path)


def managed_run(path):
    path = Path(path).resolve()
    if path.parent != RUN_ROOT.resolve() or not (path / "resolved_config.yaml").is_file():
        raise ValueError("Choose an experiment from output/experiments.")
    return path


def load_table(path):
    path = Path(path)
    if not path.is_file() or not path.stat().st_size:
        return pd.DataFrame()
    try:
        return pd.read_csv(path, sep=";", keep_default_na=False)
    except (pd.errors.EmptyDataError, pd.errors.ParserError):
        return pd.DataFrame()


def process_alive(pid):
    if not pid:
        return False
    if os.name == "nt":
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.restype = ctypes.c_void_p
        kernel.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
        kernel.GetExitCodeProcess.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong)]
        kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        handle = kernel.OpenProcess(0x1000, False, int(pid))
        if not handle:
            return False
        try:
            code = ctypes.c_ulong()
            return bool(kernel.GetExitCodeProcess(handle, ctypes.byref(code))) and code.value == 259
        finally:
            kernel.CloseHandle(handle)
    try:
        os.kill(int(pid), 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def job_status(run_dir):
    run_dir = Path(run_dir)
    if (run_dir / ".web_job.lock").exists():
        process = read_json(run_dir / "web_process.json", {})
        if process_alive(process.get("pid")):
            job = read_json(run_dir / "web_job.json", {})
            if job.get("pid") == process["pid"]:
                return job
            return {"state": "starting", "pid": process["pid"]}
        if time.time() - (run_dir / ".web_job.lock").stat().st_mtime < 10:
            return {"state": "starting"}
    job = read_json(run_dir / "web_job.json", {})
    if job.get("state") in ("starting", "running") and not process_alive(job.get("pid")):
        return {**job, "state": "interrupted"}
    return job


def list_runs():
    runs = []
    for path in sorted(RUN_ROOT.glob("*/resolved_config.yaml"), reverse=True):
        try:
            cfg = read_yaml(path)
            stage_file = path.parent / "stages.jsonl"
            events = [json.loads(line) for line in stage_file.read_text().splitlines()] if stage_file.exists() else []
            job = job_status(path.parent)
            state = job.get("state")
            if not state:
                state = "failed" if events and events[-1]["exit_code"] else (
                    "complete" if events and events[-1]["stage"] == "audit_results" else "partial")
            variant = cfg.get("query_variants", [""])[0].split("_")[0]
            models = cfg.get("models_web") or cfg.get("models_no_web") or []
            manifest = read_json(path.parent / "experiment.json", {})
            runs.append({"run": path.parent.name, "provider": cfg.get("provider", ""),
                         "variant": variant, "model": ", ".join(models),
                         "sample": manifest.get("selection", {}).get("sample", ""),
                         "rows": cfg.get("source_row_limit", 0), "status": state,
                         "path": str(path.parent)})
        except (ValueError, KeyError, TypeError, OSError, yaml.YAMLError):
            continue
    return runs


def store_upload(name, data):
    # Content-addressed inputs avoid duplicate uploads and preserve prior runs.
    import hashlib
    digest = hashlib.sha256(data).hexdigest()
    UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
    path = UPLOAD_ROOT / f"{digest}.csv"
    if not path.exists():
        path.write_bytes(data)
    return path


def prepare_config(provider, sample, variant, template, model, limit, input_path=None, query_template=None):
    args = SimpleNamespace(provider=provider, sample=sample, variant=variant, template=template,
                           model=model, mode="WEB_SEARCH", limit=limit,
                           input_path=input_path, qrels_input_path=None)
    cfg = resolve_config(read_yaml(ROOT / "experiment.yaml"), args)
    if query_template is not None:
        import string
        expected = set(VARIANT_METADATA[variant])
        if variant == "V6":
            expected.remove("abstract")
            expected.add("abstract_query")
        fields = {field for _, field, _, _ in string.Formatter().parse(query_template) if field is not None}
        if not query_template.strip() or fields != expected:
            raise ValueError("Required placeholders: " + ", ".join("{" + key + "}" for key in sorted(expected)))
        query_template.format(**{key: "Example" for key in expected})
        key = TEMPLATE_KEYS[variant]
        cfg[key] = query_template
    cfg["selected_metadata"] = list(VARIANT_METADATA[variant])
    cfg["prompt_template_name"] = template
    return cfg


def preview_queries(cfg):
    from src.generate_queries import (
        _abstract_hash, _build_queries_for_row, _contains_identifiers, _load_abstract_query_cache,
        _normalize_query, _normalize_whitespace, ABSTRACT_QUERY_TEMPLATE, QUERY_TEMPLATE, TITLE_QUERY_TEMPLATE,
        POPULATION_QUERY_TEMPLATE, POPULATION_UNIT_QUERY_TEMPLATE,
    )
    from src.load_metadata import load_metadata
    from src.prompts import build_messages, format_messages
    frame = load_metadata(cfg["input_path"], cfg["input_format"])
    limit = cfg.get("source_row_limit", 0)
    if limit:
        frame = frame.head(limit)
    cache = _load_abstract_query_cache(Path(cfg.get("abstract_query_cache_path", "output/nonexistent.csv")))
    variant = cfg["query_variants"][0]
    rows, seen, uncached = [], set(), 0
    for _, row in frame.iterrows():
        natural_query = ""
        if variant.startswith("V6_"):
            abstract = _normalize_whitespace(str(row.get("abstract", "")))
            if not abstract:
                continue
            natural_query = cache.get((str(row["id"]), _abstract_hash(abstract), cfg["abstract_query_generator_model"]), "")
            if not natural_query:
                uncached += 1
                continue
        queries = _build_queries_for_row(
            row, variant, cfg["time_format"], natural_query,
            cfg.get("title_query_template", TITLE_QUERY_TEMPLATE),
            cfg.get("metadata_query_template", QUERY_TEMPLATE),
            cfg.get("abstract_query_template", ABSTRACT_QUERY_TEMPLATE),
            cfg.get("population_query_template", POPULATION_QUERY_TEMPLATE),
            cfg.get("population_unit_query_template", POPULATION_UNIT_QUERY_TEMPLATE),
        )
        for query in queries:
            text = _normalize_whitespace(query["query_text"])
            key = _normalize_query(text)
            if not text or key in seen or _contains_identifiers(text, row):
                continue
            seen.add(key)
            rows.append({"source_dataset_id": row["id"], "query_text": text,
                         "full_prompt": format_messages(build_messages(text, cfg["top_k_return"], "WEB_SEARCH", False))})
    return pd.DataFrame(rows), len(frame), uncached


def create_run(cfg, selection):
    inputs = {key: fingerprint(cfg[key]) for key in ("input_path", "qrels_input_path")}
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    name = f"{stamp}_web_{cfg['provider']}_{cfg['query_variants'][0].split('_')[0]}_{uuid4().hex[:8]}"
    run_dir = RUN_ROOT / name
    run_dir.mkdir(parents=True, exist_ok=False)
    cfg = {**cfg, "output_dir": str(run_dir.resolve())}
    (run_dir / "resolved_config.yaml").write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
    write_json(run_dir / "experiment.json", {"created_at": datetime.now(timezone.utc).isoformat(),
                                           "selection": selection, "inputs": inputs})
    return run_dir


def launch(run_dir, stages):
    run_dir = managed_run(run_dir)
    if not stages or any(stage not in STAGES for stage in stages):
        raise ValueError("Choose valid pipeline stages.")
    lock = run_dir / ".web_job.lock"
    if lock.exists():
        if job_status(run_dir).get("state") in ("starting", "running"):
            raise ValueError("This experiment is already running.")
        lock.unlink()
    descriptor = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    os.close(descriptor)
    (run_dir / "stop.request").unlink(missing_ok=True)
    try:
        with (run_dir / "worker.log").open("a", encoding="utf-8") as log:
            flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
            process = subprocess.Popen(
                [sys.executable, "-u", "-m", "src.web_worker", "--run-dir", str(run_dir), "--stages", *stages],
                cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, creationflags=flags,
                start_new_session=os.name != "nt",
            )
        # Worker owns web_job.json. Parent records its PID separately to avoid a write race.
        write_json(run_dir / "web_process.json", {"pid": process.pid})
        return process.pid
    except Exception:
        lock.unlink(missing_ok=True)
        raise


def stop(run_dir):
    run_dir = managed_run(run_dir)
    (run_dir / "stop.request").touch()
