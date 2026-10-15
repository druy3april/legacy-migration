"""Collect current operational evidence without writing to the application databases."""

import argparse
import json
import os
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import psycopg
import pymssql
from dotenv import load_dotenv

from reconciliation.compare import Dataset, reconcile
from reconciliation.db import get_pg_connection
from reconciliation.run import check_snapshot
from reconciliation.specs import REPORTS

ROOT = Path(__file__).resolve().parents[1]


def records(connection, query):
    with connection.cursor() as cursor:
        cursor.execute(query)
        names = [column[0] for column in cursor.description]
        return [dict(zip(names, row, strict=True)) for row in cursor.fetchall()]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "docs/evidence/status-2026-10-15.json")
    args = parser.parse_args()
    load_dotenv(ROOT / ".env")
    report = {"at": datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).isoformat(), "database_writes": False}
    report["snapshot"] = check_snapshot()
    with get_pg_connection() as pg:
        pg.execute("SET TRANSACTION READ ONLY")
        params = dict(pg.info.get_parameters(), password=os.environ["POSTGRES_PASSWORD"])
        report["streak"] = records(pg, "SELECT * FROM recon.v_green_streak")[0]
        report["daily"] = records(pg, "SELECT * FROM recon.v_daily_summary ORDER BY run_date DESC LIMIT 10")
        report["latest_run"] = records(pg, "SELECT * FROM recon.runs ORDER BY started_at DESC LIMIT 1")[0]
        report["latest_build"] = records(pg, "SELECT * FROM etl.dbt_builds ORDER BY started_at DESC LIMIT 1")[0]
        report["latest_ingest"] = records(pg, "SELECT * FROM etl.ingest_batches ORDER BY finished_at DESC LIMIT 1")[0]
        report["raw"] = {}
        for name in ["customers", "products", "orders", "order_items"]:
            report["raw"][name] = records(
                pg,
                f"SELECT count(*) FILTER(WHERE _deleted_at IS NULL) AS active, "
                f"count(*) FILTER(WHERE _deleted_at IS NOT NULL) AS tombstones FROM raw.{name}",
            )[0]
    with psycopg.connect(**dict(params, dbname="metabase", options="-c default_transaction_read_only=on")) as meta:
        report["dashboards"] = records(
            meta,
            "SELECT d.id,d.name,count(c.id) AS questions,array_agg(c.id ORDER BY c.id) AS question_ids "
            "FROM report_dashboard d JOIN report_dashboardcard dc ON dc.dashboard_id=d.id "
            "JOIN report_card c ON c.id=dc.card_id WHERE d.id IN (3,4) AND NOT d.archived GROUP BY d.id,d.name "
            "ORDER BY d.id",
        )
        report["q4"] = records(meta, "SELECT id,name,dataset_query FROM report_card WHERE id=41")[0]
        sources = meta.execute(
            "SELECT DISTINCT d.id,d.engine,d.details FROM metabase_database d "
            "JOIN report_card c ON c.database_id=d.id WHERE c.id BETWEEN 44 AND 57 ORDER BY d.id"
        ).fetchall()
        cards = meta.execute(
            "SELECT id,name,database_id,dataset_query FROM report_card WHERE id BETWEEN 44 AND 57 ORDER BY id"
        ).fetchall()
    connections, datasets, query_results = {}, {}, []
    try:
        for identifier, engine, details in sources:
            details = json.loads(details) if isinstance(details, str) else details
            if engine == "sqlserver":
                connections[identifier] = pymssql.connect(
                    server=os.getenv("MSSQL_HOST", "localhost"),
                    port=int(os.getenv("MSSQL_PORT", "1433")),
                    user=details["user"],
                    password=details["password"],
                    database=details.get("dbname") or details.get("db") or "LegacyRetail",
                    timeout=20,
                )
            else:
                connections[identifier] = psycopg.connect(
                    **dict(
                        params,
                        user=details["user"],
                        password=details["password"],
                        dbname=details.get("dbname") or "warehouse",
                        options="-c default_transaction_read_only=on -c statement_timeout=20000",
                    )
                )
        tables = {spec.legacy_table for spec in REPORTS.values()} | {spec.new_table for spec in REPORTS.values()}
        for identifier, name, database_id, query in cards:
            query = json.loads(query) if isinstance(query, str) else query
            native = query["stages"][0]["native"]
            # Execute only the exact, known SELECT shape; metadata is input, not code authority.
            import re

            match = re.fullmatch(r"\s*SELECT\s+\*\s+FROM\s+([\w.]+)\s+ORDER\s+BY\s+[\w\s,]+;?\s*", native, re.I)
            if not match or match[1] not in tables:
                raise RuntimeError(f"Unexpected SELECT in question {identifier}; inspect manually")
            connection = connections[database_id]
            with connection.cursor() as cursor:
                cursor.execute(native)
                columns = [column[0] for column in cursor.description]
                rows = [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]
            datasets[match[1]] = Dataset(columns=columns, rows=rows)
            query_results.append({"id": identifier, "name": name, "status": "PASS", "rows": len(rows)})
        report["questions"] = query_results
        report["comparisons"] = []
        for name, spec in REPORTS.items():
            result = reconcile(spec, datasets[spec.legacy_table], datasets[spec.new_table], Decimal("0.01"))
            report["comparisons"].append({"report": name, "status": result.status, "diffs": len(result.diffs)})
    finally:
        for connection in connections.values():
            connection.close()
    with psycopg.connect(**dict(params, dbname="airflow", options="-c default_transaction_read_only=on")) as airflow:
        report["dags"] = records(
            airflow,
            "SELECT dag_id,is_paused,is_stale,last_parsed_time FROM dag "
            "WHERE dag_id IN ('ingest_legacy','legacy_nightly_batch','transform_dbt','reconciliation',"
            "'simulate_source_activity') ORDER BY dag_id",
        )
    report["cutover_ready"] = (
        report["streak"]["green_days"] >= int(os.getenv("CUTOVER_GREEN_DAYS", "5"))
        and report["snapshot"]["ok"]
        and report["latest_run"]["eligible_for_cutover"]
        and all(result["status"] == "PASS" for result in report["comparisons"])
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str) + "\n")
    print(f"Evidence saved: {args.output}; 14 queries; 7 comparisons; green days={report['streak']['green_days']}")
    return 0 if report["snapshot"]["ok"] and all(r["status"] == "PASS" for r in report["comparisons"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
