-include .env
export POSTGRES_USER POSTGRES_PASSWORD POSTGRES_DB POSTGRES_PORT

COMPOSE = docker compose
SQLCMD  = /opt/mssql-tools18/bin/sqlcmd

.PHONY: help env up down reset ps logs sql data batch check wh wh-sql minio extract-full load-customers ingest simulate ingest-all airflow airflow-logs airflow-pass dag-check dag-test dbt-debug dbt-build dbt-docs dbt-airflow test legacy-batch recon recon-airflow metabase lint ci-local readiness

help:
	@echo "Legacy migration - cac lenh Make"
	@echo ""
	@echo "Lenh chinh: up data wh minio airflow metabase dbt-build legacy-batch recon lint ci-local readiness"
	@echo "Dùng make <lệnh> để chạy; bên dưới có danh sách lệnh phụ."
	@echo ""
	@echo "He thong:"
	@echo "  make help            Hien thi danh sach lenh"
	@echo "  make env             Tao .env tu .env.example neu chua co"
	@echo "  make up              Khoi dong SQL Server va nap schema/thu tuc"
	@echo "  make down            Tat container, giu du lieu"
	@echo "  make reset           Tat container va xoa volume du lieu"
	@echo "  make ps              Xem trang thai container"
	@echo "  make logs            Xem log SQL Server"
	@echo "  make sql             Mo sqlcmd vao database LegacyRetail"
	@echo "  make data            Tao du lieu mau"
	@echo "  make batch           Chay batch T-SQL cu"
	@echo "  make check           Kiem tra bao cao tren SQL Server"
	@echo ""
	@echo "Warehouse va ingestion:"
	@echo "  make wh              Khoi tao PostgreSQL warehouse"
	@echo "  make wh-sql          Mo psql vao warehouse"
	@echo "  make minio           Khoi dong MinIO va tao bucket"
	@echo "  make extract-full    Trich xuat day du du lieu"
	@echo "  make load-customers  Nap customers vao PostgreSQL"
	@echo "  make ingest TABLE=orders  Nap tang dan mot bang"
	@echo "  make ingest-all      Nap tang dan tat ca bang"
	@echo "  make simulate ARGS=...    Gia lap thay doi nguon"
	@echo ""
	@echo "Airflow va dbt:"
	@echo "  make airflow         Build va khoi dong Airflow"
	@echo "  make airflow-logs    Xem log Airflow"
	@echo "  make airflow-pass    Hien thi mat khau Airflow local"
	@echo "  make dag-check       Kiem tra loi import DAG"
	@echo "  make dag-test        Chay thu DAG ingest_legacy"
	@echo "  make dbt-debug       Kiem tra ket noi dbt"
	@echo "  make dbt-build       Chay build dbt (SELECT=... de loc)"
	@echo "  make dbt-docs        Tao va phuc vu dbt docs"
	@echo "  make dbt-airflow     Chay dbt trong container Airflow"
	@echo ""
	@echo "Kiem thu, doi soat va BI:"
	@echo "  make test            Chay unit test"
	@echo "  make legacy-batch    Chay batch cu va ghi snapshot"
	@echo "  make recon           Doi soat (REPORT=daily_revenue de loc)"
	@echo "  make recon-airflow   Trigger DAG reconciliation"
	@echo "  make metabase        Khoi dong Metabase (http://localhost:$${METABASE_PORT:-3000})"
	@echo "  SQL va cau hinh dashboard: metabase/questions/ va metabase/dashboard.json"

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

test:
	.venv/bin/python -m unittest discover -s tests -v

# ---- Đối soát (Tuần 5) ----
RECON = PYTHONPATH=scripts:. .venv/bin/python -m reconciliation
REPORT ?=

legacy-batch:            ## chạy job ban đêm cũ + ghi snapshot (thay cho make batch khi đối soát)
	$(RECON).legacy_batch

recon:                   ## đối soát tất cả báo cáo, hoặc make recon REPORT=daily_revenue
	$(RECON).run $(REPORT)

recon-airflow:
	$(COMPOSE) exec airflow airflow dags trigger reconciliation

metabase:
	$(COMPOSE) up -d metabase
	@echo "Mở http://localhost:$${METABASE_PORT:-3000} (lần đầu Metabase cần 1-2 phút để khởi động)"

# ---- Tuần 6: lint + CI chạy local ----
lint:                    ## lint Python + SQL (SQLFluff cần Postgres đang chạy: make wh)
	.venv/bin/ruff check .
	.venv/bin/ruff format --check .
	.venv/bin/sqlfluff lint dbt_project/models dbt_project/tests
