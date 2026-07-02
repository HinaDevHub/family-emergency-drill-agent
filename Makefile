.PHONY: install playground run dashboard dashboard-dev test help

install:
	uv sync

playground:
	uv run adk web app --host 127.0.0.1 --port 18081 --reload_agents

run:
	uv run uvicorn app.agent_runtime_app:agent_runtime --host 127.0.0.1 --port 8000

dashboard:
	uv run uvicorn app.web_dashboard:dashboard_app --host 127.0.0.1 --port 8090

dashboard-dev:
	uv run uvicorn app.web_dashboard:dashboard_app --host 127.0.0.1 --port 8090 --reload

test:
	uv run pytest tests/unit tests/integration -v

help:
	@echo "Available commands:"
	@echo "  make install        - Install dependencies"
	@echo "  make playground     - Start ADK playground (port 18081)"
	@echo "  make dashboard      - Start web dashboard (port 8090)"
	@echo "  make dashboard-dev  - Start web dashboard with auto-reload"
	@echo "  make run            - Start agent runtime server (port 8000)"
	@echo "  make test           - Run all unit and integration tests"
