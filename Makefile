PYTHON ?= .venv/bin/python

.PHONY: db-up db-down db-schema db-current db-history db-revision db-validate db-check db-seed backend frontend check test

db-up:
	docker compose up -d postgres

db-down:
	docker compose down

db-schema:
	PYTHONPATH=backend $(PYTHON) -m alembic -c alembic.ini upgrade head

db-current:
	PYTHONPATH=backend $(PYTHON) -m alembic -c alembic.ini current

db-history:
	PYTHONPATH=backend $(PYTHON) -m alembic -c alembic.ini history

db-revision:
	@test -n "$(MESSAGE)" || (echo 'Uso: make db-revision MESSAGE="descripcion breve"' && exit 1)
	PYTHONPATH=backend $(PYTHON) -m alembic -c alembic.ini revision --autogenerate -m "$(MESSAGE)"

db-validate:
	PYTHONPATH=backend $(PYTHON) -m alembic -c alembic.ini upgrade head --sql >/dev/null

db-check:
	PYTHONPATH=backend $(PYTHON) backend/scripts/check_db.py

db-seed:
	PYTHONPATH=backend $(PYTHON) backend/scripts/load_product_seed.py

backend:
	$(PYTHON) -m uvicorn app.main:app --reload --app-dir backend

frontend:
	$(PYTHON) -m http.server 5173 --directory frontend

check:
	PYTHONPATH=. $(PYTHON) -c "from backend.app.services.availability import calculate_available_to_invoice; assert calculate_available_to_invoice(100,10,25,5)==60"

test:
	$(PYTHON) -m pytest -q
