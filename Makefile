COMPOSE = docker compose
SQLCMD  = /opt/mssql-tools18/bin/sqlcmd

.PHONY: help env up down reset ps logs sql

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