#!/bin/bash
cd "$(dirname "$0")"

uv run --env-file ../../.env uvicorn moralbench_api.main:app --reload --host 127.0.0.1 --port 8000
