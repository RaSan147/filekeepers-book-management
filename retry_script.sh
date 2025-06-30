#!/bin/bash

# --- Parse arguments ---
SCRIPT_NAME="$1"
MAX_RETRIES="${2:-3}"   # Default to 3 retries if not provided
RETRY_DELAY=60          # Delay (seconds) between retries

# --- Input validation ---
if [[ -z "$SCRIPT_NAME" ]]; then
    echo "[ERROR] Usage: $0 <script_to_run.py> [max_retries]"
    exit 1
fi

if [[ ! -f "$SCRIPT_NAME" ]]; then
    echo "[ERROR] Script '$SCRIPT_NAME' not found in $(pwd)"
    exit 1
fi

# --- Retry logic ---
for ((i=1; i<=MAX_RETRIES; i++)); do
    echo "[INFO] Attempt $i: Running $SCRIPT_NAME $([ $i -gt 1 ] && echo '--resume')"
    python3 "$SCRIPT_NAME" $([ $i -gt 1 ] && echo "--resume")

    EXIT_CODE=$?
    if [ $EXIT_CODE -eq 0 ]; then
        echo "[INFO] Success on attempt $i"
        exit 0
    else
        echo "[WARN] Attempt $i failed with exit code $EXIT_CODE"
    fi

    if [ $i -lt $MAX_RETRIES ]; then
        echo "[INFO] Retrying in $RETRY_DELAY seconds..."
        sleep $RETRY_DELAY
    fi
done

echo "[ERROR] All $MAX_RETRIES attempts failed."
exit 1
