#!/usr/bin/env bash
set -u

CONFIG="config.yaml"
VARIANTS=("V1" "V2" "V3" "V4" "V5" "V6")
STAGES=("generate_queries" "run_llm" "match_and_eval" "audit_results")
STOP_ON_ERROR=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --config)
      CONFIG="$2"
      shift 2
      ;;
    --variants)
      IFS=',' read -r -a VARIANTS <<< "$2"
      shift 2
      ;;
    --stages)
      IFS=',' read -r -a STAGES <<< "$2"
      shift 2
      ;;
    --stop-on-error)
      STOP_ON_ERROR=1
      shift
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

LOG_DIR="output/full_metadata_model_comparison"
mkdir -p "$LOG_DIR"
LOG_PATH="$LOG_DIR/run_all_variants_$(date +%Y%m%d_%H%M%S).log"

{
  echo "Config: $CONFIG"
  echo "Variants: ${VARIANTS[*]}"
  echo "Stages: ${STAGES[*]}"
  echo "Log: $LOG_PATH"

  for variant in "${VARIANTS[@]}"; do
    echo
    echo "===== Variant $variant ====="

    for stage in "${STAGES[@]}"; do
      echo
      echo "----- $stage / $variant -----"

      python -m "src.$stage" --config "$CONFIG" -V "$variant"
      exit_code=$?

      if [[ $exit_code -ne 0 ]]; then
        echo "Stage failed: $stage variant=$variant exit_code=$exit_code"
        if [[ $STOP_ON_ERROR -eq 1 ]]; then
          exit "$exit_code"
        fi
      fi
    done
  done
} 2>&1 | tee "$LOG_PATH"
