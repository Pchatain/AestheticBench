.PHONY: backend frontend

backend:
	./packages/backend/run.sh

frontend:
	cd packages/frontend && npm run dev
