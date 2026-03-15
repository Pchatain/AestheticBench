.PHONY: backend frontend tui

backend:
	./packages/backend/run.sh

frontend:
	cd packages/frontend && npm run dev

tui:
	uv run python packages/backend/src/moral_bench/annotate_tui.py
