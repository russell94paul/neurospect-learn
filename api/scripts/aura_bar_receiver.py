#!/usr/bin/env python
"""
Localhost receiver for Tradezella chart exports — Phase S1c/S1d.

The browser cannot write to disk, and pasting ~45k bars through a console return
value is neither reliable nor re-runnable. So the export is POSTed here and landed
as a file, which makes the extraction a versioned artifact instead of a paste.

    python api/scripts/aura_bar_receiver.py --out api/docs/evidence/s1d/bars --port 8791

⚠ THE LIVENESS PROBE MUST IDENTIFY *WHICH* SERVICE ANSWERED.
On 2026-08-13 this receiver was first pointed at :8765, which is held by Paul's
prefect-connectors orchestrator. That service answered the liveness probe `204`,
which read as "my server is up". It was not — the bind had failed silently and the
browser POST hung. A probe that only proves *something* is listening is not a
liveness check. `GET /whoami` therefore returns a signature string, and the browser
side refuses to POST unless it sees that exact signature.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

SIGNATURE = "aura-bar-receiver/1"

OUT_DIR = Path(".")


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _cors(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")

    def do_OPTIONS(self) -> None:          # noqa: N802
        self.send_response(204)
        self._cors()
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self) -> None:              # noqa: N802
        # The identifying probe. Anything else listening on this port will not
        # return this string, so a port collision is detected instead of assumed.
        body = SIGNATURE.encode() if self.path == "/whoami" else b"?"
        self.send_response(200)
        self._cors()
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:             # noqa: N802
        n = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(n)
        try:
            payload = json.loads(raw)
            name = payload.get("filename") or (
                "export-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + ".json"
            )
            name = Path(name).name          # never let the browser choose a directory
            dest = OUT_DIR / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(json.dumps(payload, indent=1), encoding="utf-8")
            msg = {"ok": True, "wrote": str(dest), "bytes": len(raw)}
            print(f"[receiver] wrote {dest}  ({len(raw):,} bytes)", flush=True)
        except Exception as e:              # noqa: BLE001
            msg = {"ok": False, "error": str(e)}
            print(f"[receiver] FAILED: {e}", flush=True)
        body = json.dumps(msg).encode()
        self.send_response(200)
        self._cors()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a) -> None:      # quieter; we print our own lines
        pass


def main() -> None:
    global OUT_DIR
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--port", type=int, default=8791)
    a = ap.parse_args()
    OUT_DIR = a.out
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    srv = ThreadingHTTPServer(("127.0.0.1", a.port), Handler)
    print(f"[receiver] {SIGNATURE} listening on http://127.0.0.1:{a.port} -> {OUT_DIR}",
          flush=True)
    print(f"[receiver] identify with: GET http://127.0.0.1:{a.port}/whoami", flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
