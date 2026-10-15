"""Run dbt with a recorded input batch and preserve failed/partial build attempts."""

import argparse
import json
import os
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

from psycopg.types.json import Jsonb

from reconciliation.db import get_pg_connection
from reconciliation.fingerprint import fingerprint
from reconciliation.ingest_batch import latest_ingestion


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--select")
    args = parser.parse_args()
    project = Path(os.getenv("DBT_PROJECT_DIR", str(Path(__file__).resolve().parents[1] / "dbt_project")))
    dbt = os.getenv("DBT_BIN", str(Path(sys.executable).parent / "dbt"))
    build_id = uuid.uuid4().hex
    output = Path(tempfile.mkdtemp(prefix="migration-dbt-"))
    env = dict(os.environ, DBT_TARGET_PATH=str(output / "target"), DBT_LOG_PATH=str(output / "logs"))
    with get_pg_connection() as guard:
        guard.autocommit = True
        guard.execute("SELECT pg_advisory_lock(73001)")
        try:
            batch = latest_ingestion(guard)
            before = fingerprint(guard)
            if before != batch["fingerprint"]:
                raise RuntimeError("Raw đã thay đổi sau batch hoàn tất; chạy lại ingestion")
            guard.execute(
                "INSERT INTO etl.dbt_builds(build_id,ingest_run_id,fingerprint,status) VALUES (%s,%s,%s,'RUNNING')",
                (build_id, batch["run_id"], Jsonb(before)),
            )
            status, invocation = "FAIL", None
            try:
                common = ["--project-dir", str(project), "--profiles-dir", str(project)]
                subprocess.run([dbt, "source", "freshness", *common], env=env, check=True)
                command = [dbt, "build", *common]
                if args.select:
                    command.extend(["--select", args.select])
                subprocess.run(command, env=env, check=True)
                artifact = json.loads((output / "target/run_results.json").read_text())
                manifest = json.loads((output / "target/manifest.json").read_text())
                invocation = artifact["metadata"]["invocation_id"]
                required = {
                    node_id for node_id, node in manifest["nodes"].items() if node["resource_type"] in {"model", "test"}
                }
                passed = {r["unique_id"] for r in artifact["results"] if r["status"] in {"success", "pass"}}
                if fingerprint(guard) != before:
                    raise RuntimeError("Raw thay đổi trong khi build")
                status = "PASS" if required <= passed else "PARTIAL"
            finally:
                guard.execute(
                    "UPDATE etl.dbt_builds SET status=%s,invocation_id=%s,finished_at=now(),artifact_path=%s "
                    "WHERE build_id=%s",
                    (status, invocation, str(output), build_id),
                )
            print(f"dbt {status}: build_id={build_id}; artifacts={output}")
            return 0 if status == "PASS" else 2
        finally:
            guard.execute("SELECT pg_advisory_unlock(73001)")


if __name__ == "__main__":
    sys.exit(main())
