.PHONY: backend frontend tui test lint

backend:
	uv run --env-file .env.local uvicorn aestheticbench.api.main:app --reload --host 127.0.0.1 --port 8000

frontend:
	cd web && npm run dev

tui:
	uv run python -m aestheticbench.labelling.tui

test:
	uv run python -m pytest tests -q

lint:
	uvx ruff check src tests scripts
