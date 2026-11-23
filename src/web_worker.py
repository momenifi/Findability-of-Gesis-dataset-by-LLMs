"""Execute a local UI job independently of Streamlit reruns."""

import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

from src.run_pipeline import ROOT, STAGES
from src.web_runs import managed_run, write_json


def terminate(process):
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True)
    else:
        os.killpg(process.pid, signal.SIGTERM)
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--stages", nargs="+", choices=STAGES, required=True)
    args = ap.parse_args()
    run_dir = managed_run(args.run_dir)
    state = {"pid": os.getpid(), "state": "running", "stages": args.stages,
             "started_at": datetime.now(timezone.utc).isoformat(), "stage": ""}
    process = None
    try:
        for stage in args.stages:
            if (run_dir / "stop.request").exists():
                state["state"] = "stopped"
                break
            state["stage"] = stage
            write_json(run_dir / "web_job.json", state)
            print(f"Starting {stage}", flush=True)
            with (run_dir / "console.log").open("a", encoding="utf-8") as log:
                flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
                process = subprocess.Popen(
                    [sys.executable, "-u", "-m", f"src.{stage}", "--config", str(run_dir / "resolved_config.yaml")],
                    cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, creationflags=flags,
                    start_new_session=os.name != "nt",
                )
                while process.poll() is None:
                    if (run_dir / "stop.request").exists():
                        terminate(process)
                        state["state"] = "stopped"
                        break
                    time.sleep(0.5)
                code = process.wait()
            event = {"stage": stage, "finished_at": datetime.now(timezone.utc).isoformat(), "exit_code": code}
            import json
            with (run_dir / "stages.jsonl").open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(event) + "\n")
            if state["state"] == "stopped":
                break
            if code:
                state.update(state="failed", exit_code=code)
                break
        else:
            state["state"] = "complete"
    except Exception as exc:
        state.update(state="failed", error=type(exc).__name__)
        raise
    finally:
        if process is not None and process.poll() is None:
            terminate(process)
        state["finished_at"] = datetime.now(timezone.utc).isoformat()
        write_json(run_dir / "web_job.json", state)
        (run_dir / ".web_job.lock").unlink(missing_ok=True)


if __name__ == "__main__":
    main()
