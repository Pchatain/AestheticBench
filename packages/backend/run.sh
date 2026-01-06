#!/bin/bash
cd "$(dirname "$0")"

# Set results directory (computed from script location)
export MORALBENCH_RESULTS_DIR="$(cd ../.. && pwd)/results"
echo "Results directory: $MORALBENCH_RESULTS_DIR"

uv run --env-file ../../.env uvicorn moralbench_api.main:app --reload --host 127.0.0.1 --port 8000
