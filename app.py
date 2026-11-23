"""Local research interface. Run with: streamlit run app.py"""

import os
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd
import streamlit as st
import yaml

from src.run_pipeline import ROOT, STAGES, read_yaml
from src.web_runs import (create_run, job_status, launch, list_runs, load_table,
                          prepare_config, preview_queries, stop, store_upload,
                          VARIANT_METADATA, METADATA_SOURCES, TEMPLATE_KEYS,
                          variant_for_metadata, compatible_templates)

st.set_page_config(page_title="Dataset Discovery Lab", page_icon=":material/travel_explore:", layout="wide")
st.markdown("""<style>
    .stApp { background: #fafbfc; }
    .block-container { max-width: 1500px; padding-top: 2rem; }
    h1 { font-size: 2rem !important; }
    h2 { font-size: 1.3rem !important; }
    h3 { font-size: 1.1rem !important; }
    * { letter-spacing: 0 !important; }
    [data-testid="stSidebar"] { background: #eef2f3; }
    [data-testid="stMetricValue"] { font-size: 1.7rem; }
    button { border-radius: 4px !important; }
</style>""", unsafe_allow_html=True)

CATALOG = read_yaml(ROOT / "experiment.yaml")
VARIANTS = {"V1": "All topics + country + time", "V2": "Single topic + country + time",
            "V3": "Dataset title", "V4": "Topics + country + time + population + analysis unit",
            "V5": "Topics + country + time + population", "V6": "All topics + country + time + abstract"}
FIELD_LABELS = {"title": "Title", "topic": "Topic", "country": "Country",
                "time_collection_years": "Collection time", "universe": "Population / universe",
                "analysis_unit": "Unit of analysis", "abstract": "Abstract-derived research need"}


def csv_download(frame, filename, key):
    st.download_button("Download CSV", frame.to_csv(index=False, sep=";").encode("utf-8-sig"),
                       file_name=filename, mime="text/csv", icon=":material/download:", key=key)


def show_table(frame, columns=None, height="auto"):
    if frame.empty:
        st.info("No records available.")
        return
    if columns:
        frame = frame[[column for column in columns if column in frame]]
    st.dataframe(frame, hide_index=True, width="stretch", height=height)


def open_run(path):
    st.session_state["selected_run"] = Path(path).name
    st.session_state["next_page"] = "Experiments"
    st.rerun()


def new_experiment():
    st.title("New experiment")
    left, right = st.columns([1, 1], gap="large")
    with left:
        st.subheader("Retrieval")
        provider = st.selectbox("Provider", list(CATALOG["providers"]),
                                format_func=lambda x: {"openai": "OpenAI", "gemini": "Gemini", "openwebui": "GESIS OpenWebUI"}[x])
        default = CATALOG["providers"][provider]
        model = st.text_input("Model", value=default["model"], key=f"model_{provider}")
        st.caption("Web search enabled")
        preset = st.selectbox("Metadata preset", list(VARIANTS), format_func=lambda x: f"{x} - {VARIANTS[x]}")
        fields = st.multiselect("Metadata fields", list(METADATA_SOURCES),
                               default=list(VARIANT_METADATA[preset]), format_func=lambda x: FIELD_LABELS[x],
                               key=f"fields_{preset}")
        topic_mode = st.radio("Topics per query", ["All topics", "Single topic"], horizontal=True,
                              index=1 if preset == "V2" else 0, key=f"topics_{preset}",
                              disabled=set(fields) != set(VARIANT_METADATA["V1"]))
        variant = None
        metadata_error = None
        try:
            variant = variant_for_metadata(fields, topic_mode)
            st.caption(f"Evaluation variant: {variant}")
        except ValueError as exc:
            metadata_error = str(exc)
            st.error(metadata_error)
        template = "default"
        default_text = ""
        if variant:
            options = compatible_templates(CATALOG, variant)
            if variant == "V3":
                options.sort(key=lambda value: value != "title_download")
            template = st.selectbox("Prompt template", options, key=f"template_choice_{variant}",
                                    format_func=lambda value: value.replace("_", " ").capitalize())
            default_text = CATALOG["templates"][template][TEMPLATE_KEYS[variant]]
        query_template = st.text_area("Query template", value=default_text, height=125,
                                      key=f"template_{variant}_{template}", disabled=variant is None)
        execution = st.radio("Execution", ["Generate prompts only", "Complete pipeline"], horizontal=True)
    with right:
        st.subheader("Source datasets")
        source = st.radio("Source", ["Saved sample", "Upload CSV"], horizontal=True)
        sample = st.selectbox("Dataset profile", list(CATALOG["datasets"]), disabled=source != "Saved sample",
                              format_func=lambda value: {"random100": "Random sample - 100 datasets", "top10": "Top 10 datasets"}.get(value, value))
        uploaded = st.file_uploader("Metadata CSV", type=["csv"], disabled=source != "Upload CSV")
        limit = int(st.number_input("Source row limit", min_value=0, max_value=100000, value=5, step=1,
                                    help="Uses the first rows of the selected sample; 0 uses all rows. V2 can create several queries per source dataset."))
        if source == "Saved sample":
            st.caption(CATALOG["datasets"][sample]["input_path"])
        evaluation_path = CATALOG["defaults"]["qrels_input_path"]
        st.text_input("Evaluation corpus", value=evaluation_path, disabled=True)
        env_name = default["api_key_env"]
        key_ready = bool(os.environ.get(env_name))
        st.caption(f"{env_name}: {'available' if key_ready else 'not set in server environment'}")
        st.caption("No limit on returned items. Ranking metrics use the configured evaluation cutoff.")
        if variant == "V6":
            st.caption("V6 uses the shared abstract-query cache. Missing entries require the configured generator.")
    selection = {"provider": provider, "sample": sample if source == "Saved sample" else "uploaded",
                 "variant": variant, "template": template, "limit": limit,
                 "metadata_fields": fields, "topic_mode": topic_mode,
                 "template_edited": query_template != default_text}
    cfg = None
    try:
        input_path = None
        if source == "Upload CSV":
            if uploaded is None:
                st.info("Choose a metadata CSV to continue.")
            else:
                input_path = str(store_upload(uploaded.name, uploaded.getvalue()))
        if variant and (source == "Saved sample" or uploaded is not None):
            cfg = prepare_config(provider, sample, variant, template, model.strip(), limit,
                                 input_path=input_path, query_template=query_template)
            if not model.strip():
                raise ValueError("Enter a model name.")
    except (ValueError, KeyError) as exc:
        st.error(str(exc))
    if cfg:
        with st.expander("Sample data and metadata columns"):
            st.dataframe(pd.DataFrame([{"Metadata": FIELD_LABELS[field], "Source columns": METADATA_SOURCES[field]}
                                      for field in fields]), hide_index=True, width="stretch")
            if st.button("Inspect sample", icon=":material/table_view:"):
                try:
                    from src.load_metadata import load_metadata
                    frame = load_metadata(cfg["input_path"], cfg["input_format"])
                    selected = frame.head(limit) if limit else frame
                    st.caption(f"{len(selected)} selected source rows out of {len(frame)}; showing the first 10.")
                    show_table(selected.head(10), ["id", *fields])
                except Exception as exc:
                    st.error(f"Could not read sample: {exc}")
    preview, start = st.columns([1, 1])
    if preview.button("Preview prompts", icon=":material/visibility:", disabled=cfg is None):
        try:
            with st.spinner("Preparing prompt preview..."):
                rows, selected, uncached = preview_queries(cfg)
            st.session_state["preview"] = (yaml.safe_dump(cfg), rows, selected, uncached)
        except Exception as exc:
            st.error(f"Preview failed: {type(exc).__name__}: {exc}")
    stages = ["generate_queries"] if execution == "Generate prompts only" else list(STAGES)
    label = "Generate prompts" if len(stages) == 1 else "Start experiment"
    if start.button(label, type="primary", icon=":material/play_arrow:", disabled=cfg is None):
        if len(stages) > 1 and not key_ready:
            st.error(f"Set {env_name} before starting retrieval, then restart the web server.")
        else:
            try:
                with st.spinner("Creating experiment..."):
                    run_dir = create_run(cfg, selection)
                    launch(run_dir, stages)
                open_run(run_dir)
            except Exception as exc:
                st.error(f"Could not start experiment: {type(exc).__name__}: {exc}")
    if cfg:
        previous = st.session_state.get("preview")
        if previous and previous[0] == yaml.safe_dump(cfg):
            _, rows, selected, uncached = previous
            st.divider()
            st.subheader("Prompt preview")
            st.caption(f"{selected} source rows / {len(rows)} generated queries / {uncached} uncached abstract queries")
            if uncached:
                st.warning("Uncached V6 prompts are omitted from this offline preview. Generating them may call the abstract-query model.")
            if not rows.empty:
                show_table(rows, ["source_dataset_id", "query_text"])
                choice = st.selectbox("Full prompt", range(len(rows)), format_func=lambda i: f"{i + 1} - {rows.iloc[i]['source_dataset_id']}")
                st.code(rows.iloc[choice]["full_prompt"], language=None, wrap_lines=True)
                csv_download(rows, "prompt_preview.csv", "preview_download")
        with st.expander("Resolved settings"):
            st.code(yaml.safe_dump(cfg, sort_keys=False), language="yaml")


@st.fragment(run_every=3)
def progress_panel(run_dir):
    job = job_status(run_dir)
    state_key = f"last_job_state_{run_dir.name}"
    previous = st.session_state.get(state_key)
    st.session_state[state_key] = job.get("state")
    if previous in ("starting", "running") and job.get("state") not in ("starting", "running"):
        st.rerun()
    queries = load_table(run_dir / "queries.csv")
    expected = len(queries)
    logs = list((run_dir / "logs").glob("*.json"))
    active = job.get("state") in ("starting", "running")
    a, b, c = st.columns(3)
    a.metric("Job", job.get("state", "saved").capitalize())
    b.metric("Stage", job.get("stage", "-").replace("_", " "))
    c.metric("Logged requests", f"{len(logs)} / {expected}" if expected else str(len(logs)))
    if expected:
        st.progress(min(len(logs) / expected, 1))
    if active and st.button("Stop run", icon=":material/stop:", key=f"stop_{run_dir.name}"):
        stop(run_dir)
        st.info("Stop requested.")
    if job.get("state") in ("failed", "interrupted"):
        st.error(f"Run {job['state']}. Check the execution log before continuing.")
    if job.get("state") == "complete":
        st.success("Selected stages completed.")
    for filename in ("console.log", "worker.log"):
        path = run_dir / filename
        if path.is_file():
            with st.expander(filename, expanded=active and filename == "console.log"):
                # Read only the end of the file; never display an API key from errors.
                with path.open("rb") as handle:
                    handle.seek(max(0, path.stat().st_size - 12000))
                    tail = handle.read().decode("utf-8", errors="replace")
                from src.run_llm import _redact_secrets
                st.code(_redact_secrets(tail), language=None, wrap_lines=True)


def outputs(run_dir):
    items = load_table(run_dir / "per_query_results.csv")
    if items.empty:
        items = load_table(run_dir / "llm_results.csv")
    if items.empty:
        st.info("No returned items saved yet.")
        return
    query_ids = sorted(items["query_id"].unique())
    left, right = st.columns([1, 2])
    query_id = left.selectbox("Query", ["All", *query_ids])
    filter_name = right.selectbox("Evidence", ["All items", "Strict source matches", "Relevant GESIS matches",
                                               "Title / identifier conflicts", "Explicit failure responses"])
    filtered = items if query_id == "All" else items[items.query_id == query_id]
    flag = {"Strict source matches": "is_strict_source_dataset", "Relevant GESIS matches": "is_strict_gesis_relevant_dataset",
            "Title / identifier conflicts": "title_identifier_conflict", "Explicit failure responses": "reports_not_found_without_link"}.get(filter_name)
    if flag and flag in filtered:
        filtered = filtered[filtered[flag].astype(str).isin(["1", "True"])]
    st.caption(f"{len(filtered)} returned items")
    show_table(filtered, ["query_id", "rank", "returned_title", "returned_url_or_doi", "is_strict_source_dataset",
                          "is_title_source_dataset", "is_strict_gesis_relevant_dataset", "title_identifier_conflict",
                          "claimed_data_providers", "claimed_catalogues", "justification"], height=360)
    csv_download(filtered, "filtered_model_outputs.csv", "items_download")
    if not filtered.empty:
        positions = list(range(len(filtered)))
        index = st.selectbox("Inspect returned item", positions,
                             format_func=lambda i: f"Query {filtered.iloc[i]['query_id']}, rank {filtered.iloc[i].get('rank', '-')} - {filtered.iloc[i].get('returned_title', '')}")
        row = filtered.iloc[index]
        st.subheader(str(row.get("returned_title", "")))
        link = str(row.get("returned_url_or_doi", ""))
        st.text(link or "No link returned")
        if urlparse(link).scheme.lower() in ("http", "https"):
            st.link_button("Open returned record", link, icon=":material/open_in_new:")
        st.write(str(row.get("justification", "")))
        st.json({key: row[key] for key in ("match_method", "title_match_column", "title_match_score",
                                          "repository_mentions", "claimed_data_providers", "claimed_catalogues",
                                          "reports_not_found_without_link") if key in row})


def detail(run_dir):
    cfg = read_yaml(run_dir / "resolved_config.yaml")
    st.subheader(f"{cfg['query_variants'][0].split('_')[0]} / {cfg.get('provider', '')}")
    st.caption(run_dir.name)
    overview, returned, prompts, files = st.tabs(["Overview", "Returned datasets", "Prompts", "Files & settings"])
    with overview:
        progress_panel(run_dir)
        st.divider()
        metrics = load_table(run_dir / "metrics_summary_audit.csv")
        if not metrics.empty:
            row = metrics.iloc[0]
            columns = st.columns(4)
            for col, title, key in zip(columns, ["Response coverage", "Strict source hit", "Strict relevant GESIS hit", "Title evidence hit"],
                                       ["coverage_rate", "strict_source_hit_at_k_all_queries", "strict_gesis_relevant_hit_at_k_all_queries", "title_source_hit_at_k_all_queries"]):
                col.metric(title, f"{float(row.get(key, 0)):.0%}")
            st.caption("Strict matches use catalogue identifiers. Title evidence and repository claims do not verify live links.")
            attribution = load_table(run_dir / "repository_attribution_summary.csv")
            if not attribution.empty:
                st.subheader("Repository attribution")
                show_table(attribution, ["requests", "gesis_mentioned_queries", "gesis_provider_claim_queries", "cessda_catalogue_claim_queries", "queries_with_failure_items"])
        active = job_status(run_dir).get("state") in ("starting", "running")
        a, b = st.columns(2)
        if a.button("Run retrieval & evaluation", icon=":material/play_arrow:",
                    disabled=active or not (run_dir / "queries.csv").exists(),
                    help="Calls the selected provider and replaces this experiment's retrieval results."):
            if not os.environ.get(cfg["api_key_env"]):
                st.error(f"Set {cfg['api_key_env']} in the server environment first.")
            else:
                launch(run_dir, list(STAGES[1:]))
                st.rerun()
        if b.button("Re-evaluate saved responses", icon=":material/refresh:",
                    disabled=active or not (run_dir / "llm_results.csv").exists(),
                    help="Runs matching and audit without model API calls."):
            launch(run_dir, list(STAGES[2:]))
            st.rerun()
    with returned:
        outputs(run_dir)
    with prompts:
        queries = load_table(run_dir / "queries.csv")
        if queries.empty:
            st.info("Prompts have not been generated.")
        else:
            show_table(queries, ["query_id", "source_dataset_id", "query_text"])
            index = st.selectbox("Prompt text", list(range(len(queries))),
                                 format_func=lambda i: f"Query {queries.iloc[i]['query_id']}")
            row = queries.iloc[index]
            from src.prompts import build_messages, format_messages
            mode = cfg.get("modes", ["WEB_SEARCH"])[0]
            saved_column = "full_prompt_web_search" if mode == "WEB_SEARCH" else "full_prompt_no_web"
            full = row.get(saved_column, "") or format_messages(build_messages(
                str(row.query_text), cfg["top_k_return"], mode, cfg.get("include_top_k_limit_in_prompt", False)))
            st.code(full, language=None, wrap_lines=True)
            csv_download(queries, "queries.csv", "queries_download")
    with files:
        st.code(yaml.safe_dump(cfg, sort_keys=False), language="yaml")
        available = [p.name for p in run_dir.iterdir() if p.suffix in (".csv", ".yaml", ".jsonl")]
        filename = st.selectbox("Download file", sorted(available))
        if filename:
            st.download_button("Download file", (run_dir / filename).read_bytes(), file_name=filename, icon=":material/download:")


def experiments():
    st.title("Experiments")
    runs = list_runs()
    if not runs:
        st.info("No experiments yet. Create a new experiment to begin.")
        return
    frame = pd.DataFrame(runs)
    a, b = st.columns(2)
    provider = a.selectbox("Provider filter", ["All", *sorted(frame.provider.unique())])
    variant = b.selectbox("Variant filter", ["All", *sorted(frame.variant.unique())])
    if provider != "All":
        frame = frame[frame.provider == provider]
    if variant != "All":
        frame = frame[frame.variant == variant]
    show_table(frame, ["run", "provider", "variant", "model", "sample", "rows", "status"], height=220)
    if frame.empty:
        return
    options = frame.run.tolist()
    selected = st.session_state.get("selected_run")
    if selected not in options:
        st.session_state["selected_run"] = options[0]
    name = st.selectbox("Open experiment", options, key="selected_run")
    detail(Path(frame.loc[frame.run == name, "path"].iloc[0]))


if "next_page" in st.session_state:
    st.session_state["page"] = st.session_state.pop("next_page")
with st.sidebar:
    st.markdown("### Dataset Discovery Lab")
    st.caption("GESIS / AI findability")
    page = st.radio("Workspace", ["Experiments", "New experiment"], key="page", label_visibility="collapsed")
    st.divider()
    st.caption("Local workspace")
    st.caption("OpenAI / Gemini / OpenWebUI")
    st.caption("V1 / V2 / V3 / V4 / V5 / V6")
    st.button("Refresh", icon=":material/refresh:")

if page == "New experiment":
    new_experiment()
else:
    experiments()
