"""Compare all source values, not only row counts and the largest rowversion."""

import hashlib
import json
from datetime import date, datetime
from decimal import Decimal

from ingest_incremental import TABLES


def canonical(value):
    if isinstance(value, datetime):
        return value.isoformat(timespec="microseconds")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return format(value, ".2f")
    return value


def fingerprint(conn, source=False):
    result = {}
    for name, cfg in TABLES.items():
        columns = cfg["columns"] + ["row_ver"]
        select = cfg["columns"] + (["CAST(row_ver AS BIGINT)"] if source else ["row_ver"])
        where = "" if source else " WHERE _deleted_at IS NULL"
        cursor = conn.cursor()
        try:
            cursor.execute(
                f"SELECT {', '.join(select)} FROM {'dbo' if source else 'raw'}.{name}{where} ORDER BY {cfg['key']}"
            )
            digest = hashlib.sha256()
            count, maximum = 0, None
            while rows := cursor.fetchmany(2000):
                for row in rows:
                    values = [canonical(v) for v in row]
                    if "is_active" in columns:
                        values[columns.index("is_active")] = bool(values[columns.index("is_active")])
                    digest.update(json.dumps(values, ensure_ascii=False, separators=(",", ":")).encode())
                    digest.update(b"\n")
                    count += 1
                    maximum = max(maximum or 0, int(row[-1]))
            result[name] = {"rows": count, "max_rowver": maximum, "sha256": digest.hexdigest()}
        finally:
            cursor.close()
    return result
