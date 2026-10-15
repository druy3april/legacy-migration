"""Stable local report link, gated cutover, and a reversible isolated rehearsal."""

import argparse
import json
import os
import tempfile
import threading
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, build_opener
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "metabase/active-dashboard.json"


def read_config(path):
    config = json.loads(Path(path).read_text())
    if config["active"] not in {"old", "new"}:
        raise ValueError("active must be old or new")
    for side in ["old", "new"]:
        if type(config["dashboards"][side]) is not int or config["dashboards"][side] < 1:
            raise ValueError("Dashboard IDs must be positive integers")
    return config


def target_url(config):
    base = os.getenv("METABASE_PUBLIC_URL", "http://localhost:3000").rstrip("/")
    return f"{base}/dashboard/{config['dashboards'][config['active']]}"


def server_for(path, host, port):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path not in {"/", "/healthz"}:
                self.send_error(404)
                return
            try:
                config = read_config(path)
                target = target_url(config)
            except (OSError, ValueError, KeyError):
                self.send_error(503, "Report configuration unavailable")
                return
            if self.path == "/healthz":
                body = json.dumps({"active": config["active"], "target": target}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            self.send_response(302)
            self.send_header("Location", target)
            self.send_header("Cache-Control", "no-store")
            self.end_headers()

        def log_message(self, *args):
            pass

    return ThreadingHTTPServer((host, port), Handler)


def switch(path, side, rehearsal=False):
    path = Path(path)
    config = read_config(path)
    if rehearsal and not path.name.startswith("rehearsal-"):
        raise ValueError("Rehearsal may change only a rehearsal-* configuration copy")
    if side == "new" and not rehearsal:
        from dotenv import load_dotenv

        load_dotenv(ROOT / ".env")
        from reconciliation.db import get_pg_connection
        from reconciliation.readiness import evaluate
        from reconciliation.run import check_snapshot

        with get_pg_connection() as pg:
            green, _, _, last_date = pg.execute("SELECT * FROM recon.v_green_streak").fetchone()
            latest = pg.execute(
                "SELECT eligible_for_cutover FROM recon.runs ORDER BY started_at DESC LIMIT 1"
            ).fetchone()
        today = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).date()
        reasons = evaluate(green, last_date, today, int(os.getenv("CUTOVER_GREEN_DAYS", "5")))
        if reasons or not latest or not latest[0] or not check_snapshot()["ok"]:
            raise RuntimeError("No-Go: " + "; ".join(reasons or ["latest run/snapshot is not eligible"]))
    config["active"] = side
    # Atomic replacement keeps readers from seeing a half-written configuration.
    handle, temporary = tempfile.mkstemp(prefix=".report-route-", dir=path.parent)
    try:
        with os.fdopen(handle, "w") as output:
            output.write(json.dumps(config, ensure_ascii=False, indent=2) + "\n")
        os.chmod(temporary, 0o644)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return target_url(config)


def rehearse(output):
    """Exercise a real HTTP redirect with a temporary config; keep the shared route unchanged."""
    original = DEFAULT_CONFIG.read_bytes()
    with tempfile.TemporaryDirectory(prefix="report-rehearsal-") as temporary:
        path = Path(temporary) / "rehearsal-route.json"
        path.write_bytes(original)
        switch(path, "old", rehearsal=True)
        server = server_for(path, "127.0.0.1", 0)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()

        class NoRedirect(HTTPRedirectHandler):
            def redirect_request(self, *args):
                return None

        opener = build_opener(NoRedirect())
        steps = []
        try:
            for side in ["old", "new", "old"]:
                start = time.perf_counter()
                expected = switch(path, side, rehearsal=True)
                try:
                    opener.open(f"http://127.0.0.1:{server.server_port}/", timeout=10)
                except HTTPError as result:
                    assert result.code == 302 and result.headers["Location"] == expected
                else:
                    raise RuntimeError("Expected HTTP 302")
                steps.append({"side": side, "location": expected, "observed_seconds": time.perf_counter() - start})
        finally:
            server.shutdown()
            server.server_close()
            worker.join(timeout=2)
    assert DEFAULT_CONFIG.read_bytes() == original
    report = {
        "at": datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).isoformat(),
        "scope": "isolated rehearsal of actual HTTP route; shared route unchanged; not Go approval or human RTO",
        "steps": steps,
        "passed": True,
    }
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(f"REHEARSAL PASS: OLD -> NEW -> OLD; {output}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["serve", "status", "old", "new", "rehearse"])
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=3001)
    parser.add_argument("--output", default="docs/evidence/cutover-rehearsal-2026-10-15.json")
    args = parser.parse_args()
    if args.action == "serve":
        server_for(args.config, args.host, args.port).serve_forever()
    elif args.action == "status":
        print(target_url(read_config(args.config)))
    elif args.action == "rehearse":
        rehearse(args.output)
    else:
        print(switch(args.config, args.action))


if __name__ == "__main__":
    main()
