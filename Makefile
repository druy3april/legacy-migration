-include .env
export POSTGRES_USER POSTGRES_PASSWORD POSTGRES_DB POSTGRES_PORT

COMPOSE = docker compose
SQLCMD  = /opt/mssql-tools18/bin/sqlcmd

.PHONY: help env up down reset ps logs sql data batch check wh wh-sql minio extract-full load-customers ingest simulate ingest-all airflow airflow-logs airflow-pass dag-check dag-test dbt-debug dbt-build dbt-docs dbt-airflow

help:
	@echo "make up    - dung SQL Server va nap file sql/*.sql"
	@echo "make sql   - mo sqlcmd vao database LegacyRetail"
	@echo "make ps    - xem trang thai container"
	@echo "make down  - tat container, giu du lieu"
	@echo "make reset - tat container va XOA du lieu"

env:
	@test -f .env || (cp .env.example .env && echo "Da tao .env")

up: env
	$(COMPOSE) up -d sqlserver
	$(COMPOSE) run --rm sql-init

sql:
	$(COMPOSE) exec sqlserver bash -c '$(SQLCMD) -C -S localhost -U sa -P "$$MSSQL_SA_PASSWORD" -d LegacyRetail'

ps:
	$(COMPOSE) ps

logs:
	$(COMPOSE) logs --tail=100 sqlserver

down:
	$(COMPOSE) down

reset:
	$(COMPOSE) down -v

data:
	python scripts/generate_data.py

batch:
	$(COMPOSE) exec -T sqlserver bash -c '$(SQLCMD) -C -S localhost -U sa -P "$$MSSQL_SA_PASSWORD" -d LegacyRetail -b -Q "EXEC dbo.sp_run_nightly_batch"'

check:
	$(COMPOSE) exec -T sqlserver bash -c '$(SQLCMD) -C -S localhost -U sa -P "$$MSSQL_SA_PASSWORD" -d LegacyRetail -W' < scripts/check.sql

wh:
	$(COMPOSE) up -d --wait postgres
	$(COMPOSE) exec -T postgres bash -c 'psql -v ON_ERROR_STOP=1 -U "$$POSTGRES_USER" -d "$$POSTGRES_DB"' < warehouse/init.sql

wh-sql:
	$(COMPOSE) exec postgres bash -c 'psql -U "$$POSTGRES_USER" -d "$$POSTGRES_DB"'

minio:
	$(COMPOSE) up -d minio
	python scripts/init_minio.py

extract-full:
	python scripts/extract_full.py

load-customers:
	python scripts/load_to_postgres.py

TABLE ?= customers

ingest:
	python scripts/ingest_incremental.py $(TABLE)

ARGS ?=

simulate:
	python scripts/simulate_changes.py $(ARGS)

ingest-all:
	python scripts/ingest_incremental.py all

airflow:
	$(COMPOSE) up -d --build airflow

airflow-logs:
	$(COMPOSE) logs --tail=80 airflow

airflow-pass:
	$(COMPOSE) exec airflow cat /opt/airflow/simple_auth_manager_passwords.json.generated

dag-check:
	$(COMPOSE) exec airflow airflow dags list-import-errors

dag-test:
	$(COMPOSE) exec airflow airflow dags test ingest_legacy

# ---- dbt (Tuan 3-4) ----
DBT_LOCAL = cd dbt_project && ../.venv/bin/dbt
DBT_IN_AIRFLOW = $(COMPOSE) exec -e DBT_PROFILES_DIR=/opt/airflow/dbt_project -e DBT_TARGET_PATH=/tmp/dbt_target -e DBT_LOG_PATH=/tmp/dbt_logs -w /opt/airflow/dbt_project airflow /home/airflow/dbt-venv/bin/dbt
SELECT ?=

dbt-debug:
	$(DBT_LOCAL) debug --profiles-dir .

dbt-build:
	$(DBT_LOCAL) build --profiles-dir . $(if $(SELECT),-s $(SELECT),)

dbt-docs:
	$(DBT_LOCAL) docs generate --profiles-dir .
	$(DBT_LOCAL) docs serve --profiles-dir . --port 8081

dbt-airflow:
	$(DBT_IN_AIRFLOW) build