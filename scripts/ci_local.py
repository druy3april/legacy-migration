"""Run CI in a newly created test_* database and remove only that database afterwards."""

import os
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from load_to_postgres import get_pg_connection
from psycopg import sql


def main():
    load_dotenv()
    root = Path(__file__).resolve().parents[1]
    binary = Path(sys.executable).parent
    name = "test_ci_" + uuid.uuid4().hex[:12]
    output = Path(tempfile.mkdtemp(prefix="legacy-ci-"))
    with get_pg_connection() as original:
        params = dict(original.info.get_parameters(), password=os.environ["POSTGRES_PASSWORD"])
    env = dict(
        os.environ,
        POSTGRES_DB=name,
        MIGRATION_TEST_DB=name,
        PGDATABASE=name,
        PGUSER=params["user"],
        PGPASSWORD=params["password"],
        PGHOST=params["host"],
        PGPORT=str(params.get("port", "5432")),
        DBT_TARGET_PATH=str(output / "target"),
        DBT_LOG_PATH=str(output / "logs"),
        DBT_SEND_ANONYMOUS_USAGE_STATS="false",
    )

    def step(label, command, content=None):
        print(f"\n--- {label} ---", flush=True)
        subprocess.run(command, input=content, text=True, cwd=root, env=env, check=True)

    def load(path):
        command = (
            ["psql", "-v", "ON_ERROR_STOP=1"]
            if shutil.which("psql")
            else [
                "docker",
                "compose",
                "exec",
                "-T",
                "postgres",
                "psql",
                "-U",
                params["user"],
                "-d",
                name,
                "-v",
                "ON_ERROR_STOP=1",
            ]
        )
        step(str(path), command, (root / path).read_text())

    with psycopg.connect(**dict(params, dbname="postgres"), autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            load(Path("warehouse/init.sql"))
            load(Path("ci/sample_raw_data.sql"))
            step("Ruff", [str(binary / "ruff"), "check", "."])
            step("Format", [str(binary / "ruff"), "format", "--check", "."])
            step("Unit + SQL integration tests", [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"])
            common = ["--project-dir", str(root / "dbt_project"), "--profiles-dir", str(root / "dbt_project")]
            for action in ["compile", "build", "source freshness"]:
                step("dbt " + action, [str(binary / "dbt"), *action.split(), *common])
            load(Path("ci/assert_expected_marts.sql"))
            step("SQLFluff", [str(binary / "sqlfluff"), "lint", "dbt_project/models", "dbt_project/tests"])
            print(f"CI PASS; artifacts: {output}")
        finally:
            admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
