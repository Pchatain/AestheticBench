#!/bin/bash
cd "$(dirname "$0")"

# Set results directory (computed from script location)
export AESTHETICBENCH_RESULTS_DIR="$(cd ../.. && pwd)/results"
echo "Results directory: $AESTHETICBENCH_RESULTS_DIR"
echo "pwd: $(pwd)"
env_file="$(pwd)/../../.env.local"
echo "env_file: $env_file"
uv run --env-file $env_file uvicorn aestheticbench_api.main:app --reload --host 127.0.0.1 --port 8000
