"""
LLM Dataset Discovery Pipeline
===============================
Purpose: Queries Gemma, Llama, and GPT via GESIS OpenWebUI to test
         how well they can find GESIS datasets based on metadata.
Input:   A CSV file containing metadata for 100 GESIS studies.
Output:  A TSV file with the generated responses and a printed summary.
Steps:
         1. Load OpenWebUI API key from environment or .env file.
         2. Load and sample datasets from the input CSV (Test or Full mode).
         3. Parse and format dataset metadata (e.g., calculating decades).
         4. Build targeted prompts using a predefined template.
         5. Query multiple LLM endpoints via the OpenWebUI API.
         6. Evaluate the LLM responses for GESIS mentions and exact matches.
         7. Export results to a TSV file and output a statistical summary.
Author:  Soufian El Berkani
Date:    2026-05-11
Source:  llm_discovery.py
"""

import os
import ast
import json
import time
import logging
import requests
import pandas as pd
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Configuration & Constants
# ---------------------------------------------------------------------------
API_URL = "https://ai-openwebui.gesis.org/api/chat/completions"
MODELS = ["gemma3:27b", "gpt-4.1", "gpt-4.1-mini",
          "llama4:latest","o4-mini","gpt-5",
          "gpt-5-mini", "gpt-5.1", "gpt-5.4",
          "gpt-oss:120b", "gpt-oss:latest", "mistral-small3.2:latest"
          ]

INPUT_CSV = os.path.join(os.path.dirname(__file__), "random_100_datasets_full_metadata.csv")

OUTPUT_CSV = os.path.join(os.path.dirname(__file__), "outputs", "results.tsv")

RUN_MODE = "test"  # Set to "full" to process 100 datasets

TEST_DATASET_IDS = [
    "ZA0401", "ZA0322", "ZA3680", "ZA0265", "ZA4456",
    "ZA8286", "ZA8859", "ZA2235", "ZA0840", "SDN-10.7802-1754"
]

MAX_RETRIES = 3
RETRY_BACKOFF = 2  # seconds, doubles each retry
REQUEST_TIMEOUT = 120

# Column indices
COL_DATASET_ID = 2
COL_TIME_YEARS = 16
COL_COUNTRIES_EN = 69
COL_TOPICS_EN = 73

PROMPT_TEMPLATE = (
    "Can you find datasets related to {topic} in {countries} during the {decade}?"
)

# ---------------------------------------------------------------------------
# Logging Configuration
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(
            os.path.join(os.path.dirname(__file__), "pipeline.log"),
            encoding="utf-8",
        ),
    ],
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def parse_json_list(raw: str) -> list[str]:
    """
    Safely parse a JSON-encoded list stored as a CSV cell.
    """
    if pd.isna(raw) or not raw:
        return []
        
    try:
        # Attempt to safely evaluate the string as a Python literal
        parsed = ast.literal_eval(raw)
        if isinstance(parsed, list):
            return [str(x).strip() for x in parsed if str(x).strip()]
        return [str(parsed).strip()]
    except (ValueError, SyntaxError):
        try:
            # Fallback to JSON parsing if literal_eval fails
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return [str(x).strip() for x in parsed if str(x).strip()]
            return [str(parsed).strip()]
        except json.JSONDecodeError:
            # Return as a single-element list if all parsing fails
            return [raw.strip()] if raw.strip() else []


def years_to_decade(years: list[str]) -> str:
    """
    Convert a list of year strings to a decade label, e.g., '1970s'.
    """
    numeric = []
    for y in years:
        try:
            # Convert string to float first, then int, to handle inputs like '1971.0'
            numeric.append(int(float(y)))
        except (ValueError, TypeError):
            continue
     # Return default string if no valid years were found        
    if not numeric:
        return "unknown decade"
    
    # Calculate decade based on the earliest year in the list    
    earliest = min(numeric)
    return f"{(earliest // 10) * 10}s"


def query_llm(model: str, prompt: str, api_key: str) -> str:
    """
    Send a prompt to OpenWebUI and return the response text.
    """
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    
    messages = [{"role": "user", "content": prompt}]

    payload = {
        "model": model,
        "messages": messages,
    }

    # Attempt the API call with retries and exponential backoff
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.post(
                API_URL,
                headers=headers,
                json=payload,
                timeout=REQUEST_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]
        except Exception as exc:
            wait = RETRY_BACKOFF ** attempt
            log.warning(
                "Attempt %d/%d for %s failed: %s — retrying in %ds",
                attempt, MAX_RETRIES, model, exc, wait,
            )
            time.sleep(wait)

    log.error("All %d attempts failed for model=%s", MAX_RETRIES, model)
    return "[ERROR] All retries failed."


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def main():
    """
    Main execution function for the LLM Dataset Discovery Pipeline.
    """
    # --- Load API key ---
    api_key = os.environ.get("OPENWEBUI_API_KEY", "")
    if not api_key:
        env_path = os.path.join(os.path.dirname(__file__), ".env")
        if os.path.exists(env_path):
            with open(env_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("OPENWEBUI_API_KEY="):
                        api_key = line.split("=", 1)[1].strip().strip('"').strip("'")
                        
    if not api_key:
        log.error("No API key found. Set OPENWEBUI_API_KEY env var or create a .env file.")
        return

    # --- Load CSV ---
    input_path = os.path.normpath(INPUT_CSV)
    log.info("Loading CSV from %s", input_path)
    
    df = pd.read_csv(input_path, header=0, on_bad_lines="skip", engine="python", dtype=str)

    df.fillna("", inplace=True)

    log.info("Full CSV: %d rows, %d columns", len(df), len(df.columns))

    # --- Test vs. Full Run Logic ---
    if RUN_MODE == "test":
        log.info("TEST MODE active: Filtering for fixed test IDs.")
        # Filter the DataFrame to keep only the rows with IDs in our test list
        sample = df[df.iloc[:, COL_DATASET_ID].astype(str).str.strip().isin(TEST_DATASET_IDS)]
    else:
        log.info("FULL MODE active: Using all datasets.")
        sample = df  

    log.info("Processing %d datasets", len(sample))

    # --- Prepare output dir ---
    os.makedirs(os.path.dirname(OUTPUT_CSV), exist_ok=True)

    # --- Build prompts and query ---
    results = []
    total_prompts = 0

    for _, row in sample.iterrows():
        dataset_id = str(row.iloc[COL_DATASET_ID]).strip()
        years = parse_json_list(str(row.iloc[COL_TIME_YEARS]))
        countries = parse_json_list(str(row.iloc[COL_COUNTRIES_EN]))
        topics = parse_json_list(str(row.iloc[COL_TOPICS_EN]))

        if not topics:
            log.warning("Dataset %s has no topics — skipping", dataset_id)
            continue

        decade_str = years_to_decade(years)
        countries_str = ", ".join(countries) if countries else "unknown location"
        
        for topic in topics:
            prompt = PROMPT_TEMPLATE.format(
                topic=topic,
                countries=countries_str,
                decade=decade_str,
            )
            total_prompts += 1

            for model in MODELS:
                log.info("[%s] Querying %s — topic='%s'", dataset_id, model, topic)
                ts = datetime.now(timezone.utc).isoformat()
                
                answer = query_llm(model, prompt, api_key)

                if answer is None:
                    answer = "[ERROR: API returned None]"
                    log.warning("[%s] %s returned None/empty response", dataset_id, model)
                # --- Evaluate the response ---
                mentions_gesis = "gesis" in answer.lower()
                found_exact_id = dataset_id.lower() in answer.lower()
                
                # Differentiate between DBK (ZA...) and SowiDataNet (SDN...)
                if dataset_id.startswith("SDN-"):
                    target_number = dataset_id.split("-")[-1]
                    found_doi = f"10.7802/{target_number}" in answer
                else:
                    target_number = dataset_id.replace("ZA", "").strip()
                    found_doi = f"10.4232/1.{target_number}" in answer
                    
                found_target_study = bool(found_exact_id or found_doi)
                
                # Append structured results
                results.append({
                    "dataset_id": dataset_id,
                    "model": model,
                    "prompt": prompt,
                    "answer": answer,
                    "mentions_gesis": mentions_gesis,
                    "found_target_study": found_target_study,
                    "timestamp": ts,
                })

    log.info(
        "Done. %d prompts × %d models = %d total queries",
        total_prompts, len(MODELS), len(results),
    )

    # --- Save results as TSV ---
    out_df = pd.DataFrame(results)
    if not out_df.empty:
        
        out_df.to_csv(OUTPUT_CSV, index=False, sep='\t')
        log.info("Results saved to %s", os.path.normpath(OUTPUT_CSV))

        # --- Quick summary ---
        summary = out_df.groupby("model")["mentions_gesis"].agg(["sum", "count"])
        summary.columns = ["gesis_mentions", "total"]
        summary["mention_rate"] = (summary["gesis_mentions"] / summary["total"] * 100).round(1)
        
        print("\nSummary")
        print(summary.to_string())
        print(f"\nTotal results: {len(out_df)}")
        print(f"Output: {os.path.normpath(OUTPUT_CSV)}")
    else:
        log.warning("No results generated.")


if __name__ == "__main__":
    main()