#!/bin/bash
cd "$(dirname "$0")"

# Copy results from main directory into backend data folder
rm -rf data/results
mkdir -p data
cp -r ../../results data/results

echo "Copied results to data/results"

uv run uvicorn moralbench_api.main:app --reload --host 127.0.0.1 --port 8000
