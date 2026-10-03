COMPOSE = docker compose
SQLCMD  = /opt/mssql-tools18/bin/sqlcmd

.PHONY: help env up down reset ps logs sql data batch check

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