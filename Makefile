PYTHON ?= python3

.PHONY: db-up db-down db-schema db-seed backend frontend check test

db-up:
	docker compose up -d postgres

db-down:
	docker compose down

db-schema:
	PYTHONPATH=backend $(PYTHON) backend/scripts/apply_schema.py

db-seed:
	PYTHONPATH=backend $(PYTHON) backend/scripts/load_product_seed.py

backend:
	uvicorn app.main:app --reload --app-dir backend

frontend:
	$(PYTHON) -m http.server 5173 --directory frontend

check:
	PYTHONPATH=. $(PYTHON) -c "from backend.app.services.availability import calculate_available_to_invoice; assert calculate_available_to_invoice(100,10,25,5)==60"

test:
	.venv/bin/python -m pytest -q
