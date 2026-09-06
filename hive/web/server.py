"""Web backend — serves TSX dashboard + audited API.

Local-first: no egress, all data from ~/.hive/* DBs and local LLM health.
"""

from __future__ import annotations

import json
import urllib.parse
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from typing import Optional

from hive.config import load_config
from hive.machine import MACHINE_DIR, WORKSPACE
from hive.machine.audit import query_audit, stats, verify_chain
from hive.research.session import list_sessions
from hive.machine.workflows import list_workflows

WEB_DIST = Path(__file__).parent.parent.parent / "web" / "dist"
WEB_SRC = Path(__file__).parent.parent.parent / "web" / "src"

class WebHandler(SimpleHTTPRequestHandler):
    def _set_headers(self, ctype="application/json", status=200):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_OPTIONS(self):
        self._set_headers("text/plain", 200)
        self.wfile.write(b"")

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        qs = urllib.parse.parse_qs(parsed.query)

        # ── API ───────────────────────────────────────────────────
        if path == "/api/health":
            self._api_health()
            return
        if path == "/api/models":
            self._api_models()
            return
        if path == "/api/audit":
            limit = int(qs.get("limit", ["50"])[0])
            min_sev = int(qs.get("min_severity", ["0"])[0])
            self._api_audit(limit, min_sev)
            return
        if path == "/api/stats":
            self._api_stats()
            return
        if path == "/api/verify":
            self._api_verify()
            return
        if path == "/api/sessions":
            self._api_sessions()
            return
        if path == "/api/workflows":
            self._api_workflows()
            return
        if path == "/api/files":
            self._api_files()
            return
        if path == "/api/nvidia":
            self._api_nvidia()
            return
        if path == "/api/export":
            self._api_export()
            return

        # ── static — serve web/dist if built, else fallback ─────
        if WEB_DIST.exists() and (WEB_DIST / "index.html").exists():
            # serve dist
            rel = path.lstrip("/") or "index.html"
            # sanitize
            target = (WEB_DIST / rel).resolve()
            if not str(target).startswith(str(WEB_DIST.resolve())):
                self._set_headers("text/plain", 403)
                self.wfile.write(b"forbidden")
                return
            if target.is_dir():
                target = target / "index.html"
            if target.exists():
                # guess ctype
                ctype = "text/html"
                if target.suffix == ".js":
                    ctype = "application/javascript"
                elif target.suffix == ".css":
                    ctype = "text/css"
                elif target.suffix == ".json":
                    ctype = "application/json"
                self._set_headers(ctype, 200)
                self.wfile.write(target.read_bytes())
                return
            # fallback to index.html for SPA
            self._set_headers("text/html", 200)
            self.wfile.write((WEB_DIST / "index.html").read_bytes())
            return

        # dev fallback: serve simple placeholder with instructions
        if path == "/" or path == "/index.html":
            self._set_headers("text/html", 200)
            html = """<!doctype html><html><head><meta charset="utf-8"><title>Hive Web</title>
            <style>body{font-family:system-ui;background:#0b0e14;color:#e6e8ec;padding:40px} a{color:#4f8cff} code{background:#11151d;border:1px solid #1f2533;padding:2px 6px;border-radius:4px}</style></head><body>
            <h1>Hive Research - A Local research companion — Web Dashboard</h1>
            <p>TSX build not found. Build it:</p>
            <pre><code>cd web && npm install && npm run build</code></pre>
            <p>Then <code>hive serve --web</code> or <code>hive web</code> will serve <code>web/dist</code> on <code>http://localhost:8000</code>.</p>
            <p>API is live:</p>
            <ul><li><a href="/api/health">/api/health</a></li><li><a href="/api/audit?limit=5">/api/audit</a></li><li><a href="/api/stats">/api/stats</a></li><li><a href="/api/verify">/api/verify</a></li></ul>
            <p>For dev (hot reload): <code>cd web && npm run dev</code> (proxies /api to :8000)</p>
            </body></html>"""
            self.wfile.write(html.encode())
            return

        # fallback 404
        self._set_headers("text/plain", 404)
        self.wfile.write(b"not found")

    # ── API implementations ──────────────────────────────────────

    def _api_health(self):
        from hive.llm.ollama import OllamaProvider
        from hive.llm.lmstudio import LMStudioProvider
        from hive.llm.nvidia import NvidiaProvider
        import httpx
        cfg = load_config()
        res = {}
        for label, prov in [
            ("ollama", OllamaProvider(cfg.llm.ollama_url, cfg.llm.ollama_model)),
            ("lmstudio", LMStudioProvider(cfg.llm.lmstudio_url, cfg.llm.lmstudio_model)),
            ("nvidia", NvidiaProvider(cfg.llm.nvidia_url, cfg.llm.nvidia_model)),
        ]:
            ok, msg = prov.health()
            res[label] = f"ok ({msg})" if ok else msg
        # paper APIs
        for name, url in [("openalex", "https://api.openalex.org/works?search=test&per-page=1"), ("arxiv", "https://export.arxiv.org/api/query?search_query=all:test&max_results=1")]:
            try:
                with httpx.Client(timeout=5) as c:
                    r = c.get(url)
                    res[name] = str(r.status_code)
            except Exception as e:
                res[name] = str(e)
        self._set_headers()
        self.wfile.write(json.dumps(res).encode())

    def _api_models(self):
        from hive.machine.nvidia_pair import discover_all
        cfg = load_config()
        models = discover_all(cfg)
        self._set_headers()
        self.wfile.write(json.dumps([m.__dict__ for m in models]).encode())

    def _api_audit(self, limit: int, min_sev: int):
        rows = query_audit(limit=limit, min_severity=min_sev)
        self._set_headers()
        self.wfile.write(json.dumps(rows).encode())

    def _api_stats(self):
        s = stats()
        self._set_headers()
        self.wfile.write(json.dumps({"total": s["total"], "by_tool": s["by_tool"]}).encode())

    def _api_verify(self):
        ok, msg = verify_chain()
        self._set_headers()
        self.wfile.write(json.dumps({"ok": ok, "msg": msg}).encode())

    def _api_sessions(self):
        rows = list_sessions(limit=30)
        self._set_headers()
        self.wfile.write(json.dumps(rows).encode())

    def _api_workflows(self):
        wfs = list_workflows()
        self._set_headers()
        self.wfile.write(json.dumps([{"name": p.stem, "path": str(p)} for p in wfs]).encode())

    def _api_files(self):
        WORKSPACE.mkdir(parents=True, exist_ok=True)
        items = []
        for p in sorted(WORKSPACE.iterdir()):
            try:
                items.append({"path": p.name, "type": "dir" if p.is_dir() else "file", "size": p.stat().st_size})
            except Exception:
                continue
        self._set_headers()
        self.wfile.write(json.dumps(items).encode())

    def _api_nvidia(self):
        from hive.machine.nvidia_pair import discover_all, nvidia_smi_info
        cfg = load_config()
        gpu = nvidia_smi_info()
        models = discover_all(cfg)
        self._set_headers()
        self.wfile.write(json.dumps({"gpu": gpu, "models": [m.__dict__ for m in models]}).encode())

    def _api_export(self):
        from hive.machine.audit import export_proofs
        out = export_proofs()
        self._set_headers()
        self.wfile.write(json.dumps(out).encode())


def run_web(host: str = "127.0.0.1", port: int = 8000, open_browser: bool = False):
    # ensure machine dirs
    MACHINE_DIR.mkdir(parents=True, exist_ok=True)
    WORKSPACE.mkdir(parents=True, exist_ok=True)
    addr = (host, port)
    # if web/dist exists, serve from there; else use handler fallback
    # we set directory to WEB_DIST if exists, else MACHINE_DIR
    handler = WebHandler
    # override directory for SimpleHTTPRequestHandler
    import os
    os.chdir(WEB_DIST if WEB_DIST.exists() else MACHINE_DIR)
    httpd = HTTPServer(addr, handler)
    print(f"Hive Web — http://{host}:{port}  (api: /api/health, /api/audit, /api/stats, etc.)")
    if WEB_DIST.exists():
        print(f"Serving TSX build: {WEB_DIST}")
    else:
        print(f"TSX not built — run: cd web && npm install && npm run build  — serving fallback + API")
    if open_browser:
        import webbrowser
        webbrowser.open(f"http://{host}:{port}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped")
