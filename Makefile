-include .env
export POSTGRES_USER POSTGRES_PASSWORD POSTGRES_DB POSTGRES_PORT
PYTHON = .venv/bin/python

COMPOSE = docker compose
SQLCMD  = /opt/mssql-tools18/bin/sqlcmd

.PHONY: help env up down reset ps logs sql data batch check wh wh-sql minio extract-full load-customers ingest simulate ingest-all airflow airflow-logs airflow-pass dag-check dag-test dbt-debug dbt-build dbt-docs dbt-airflow test legacy-batch recon recon-airflow metabase lint ci-local readiness tf-init tf-fmt tf-validate tf-plan

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
	@echo ""
	@echo "Tuan 6 - CI, Terraform, cutover:"
	@echo "  make lint            Ruff + SQLFluff (can Postgres dang chay: make wh)"
	@echo "  make ci-local        Database test rieng + lint/test/dbt/golden + Terraform"
	@echo "  make readiness       Kiem tra du CUTOVER_GREEN_DAYS ngay doi soat xanh lien tiep"
	@echo "  make audit           Thu thap bang chung van hanh (chi doc database)"
	@echo "  make reports         Link chung OLD/NEW http://localhost:3001"
	@echo "  make rehearse        Dien tap HTTP route tren config tam"
	@echo "  make cutover         Chuyen NEW khi du dieu kien; make rollback de ve OLD"
	@echo "  make tf-fmt          Dinh dang lai code Terraform"
	@echo "  make tf-validate     terraform fmt -check + validate"
	@echo "  make tf-plan         terraform plan voi khoa gia (khong can tai khoan AWS)"

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
	$(PYTHON) scripts/generate_data.py

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
	$(PYTHON) scripts/init_minio.py

extract-full:
	$(PYTHON) scripts/extract_full.py

load-customers:
	$(PYTHON) scripts/load_to_postgres.py

TABLE ?= customers

ingest:
	PYTHONPATH=scripts:. $(PYTHON) scripts/ingest_incremental.py $(TABLE)

ARGS ?=

simulate:
	$(PYTHON) scripts/simulate_changes.py $(ARGS)

ingest-all:
	PYTHONPATH=scripts:. $(PYTHON) scripts/ingest_incremental.py all

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
	PYTHONPATH=scripts:. $(PYTHON) -m reconciliation.build $(if $(SELECT),--select "$(SELECT)",)

dbt-docs:
	$(DBT_LOCAL) docs generate --profiles-dir .
	$(DBT_LOCAL) docs serve --profiles-dir . --port 8081

dbt-airflow:
	$(COMPOSE) exec -e DBT_BIN=/home/airflow/dbt-venv/bin/dbt -e DBT_PROJECT_DIR=/opt/airflow/dbt_project airflow python -m reconciliation.build

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

ci-local:   ## database test cô lập + cùng các kiểm tra như CI
	PYTHONPATH=scripts:. $(PYTHON) scripts/ci_local.py
	$(MAKE) tf-validate tf-plan
	@echo "ci-local: tất cả các bước đều xanh"

readiness:               ## exit 0 khi đủ điều kiện cutover (docs/cutover_plan.md)
	$(RECON).readiness

# ---- Terraform (chỉ plan, không apply) ----
TF = terraform -chdir=terraform

tf-init:
	@command -v terraform >/dev/null || { echo "Chưa cài terraform, xem terraform/README.md"; exit 1; }
	$(TF) init -input=false

tf-fmt:
	$(TF) fmt -recursive

tf-validate: tf-init
	$(TF) fmt -check -recursive
	$(TF) validate

tf-plan: tf-init
	$(TF) plan -input=false -lock=false

.PHONY: restore-raw integration-test

integration-test:
	PYTHONPATH=scripts:. $(PYTHON) scripts/integration_lab.py

# MANIFEST=manifests/<sha256>.json RESTORE_DB=restore_lab
restore-raw:
	@test -n "$(MANIFEST)" && test -n "$(RESTORE_DB)"
	PYTHONPATH=scripts:. $(PYTHON) scripts/archive_raw.py "$(MANIFEST)" --database "$(RESTORE_DB)"

.PHONY: reports reports-status cutover rollback rehearse audit
reports:
	$(COMPOSE) up -d reports
reports-status:
	$(PYTHON) scripts/report_portal.py status
cutover:
	PYTHONPATH=scripts:. $(PYTHON) scripts/report_portal.py new
rollback:
	$(PYTHON) scripts/report_portal.py old
rehearse:
	$(PYTHON) scripts/report_portal.py rehearse
audit:
	PYTHONPATH=scripts:. $(PYTHON) scripts/collect_evidence.py
