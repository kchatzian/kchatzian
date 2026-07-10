#!/usr/bin/env python3
import json
import subprocess
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "portfolio-projects.json"
GENERATOR = ROOT / "scripts" / "generate_portfolio_section.py"

HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Portfolio Projects</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: #0b1020;
      --panel: #111827;
      --panel-2: #172033;
      --line: #2a3a4d;
      --text: #e5e7eb;
      --muted: #94a3b8;
      --accent: #00c2a8;
      --accent-2: #38bdf8;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font: 14px/1.45 Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      padding: 22px 28px;
      border-bottom: 1px solid var(--line);
      background: #0d1426;
    }
    h1 {
      margin: 0;
      font-size: 20px;
      letter-spacing: 0;
    }
    main { padding: 24px 28px 36px; }
    .actions {
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
      align-items: center;
    }
    button, select, input, textarea {
      border: 1px solid var(--line);
      border-radius: 6px;
      background: var(--panel);
      color: var(--text);
      font: inherit;
    }
    button {
      cursor: pointer;
      padding: 9px 12px;
      font-weight: 700;
    }
    button.primary {
      background: var(--accent);
      border-color: var(--accent);
      color: #041312;
    }
    button.secondary {
      background: var(--panel-2);
    }
    table {
      width: 100%;
      border-collapse: collapse;
      border: 1px solid var(--line);
      background: var(--panel);
    }
    th, td {
      border-bottom: 1px solid var(--line);
      padding: 10px;
      vertical-align: top;
      text-align: left;
    }
    th {
      position: sticky;
      top: 0;
      z-index: 1;
      background: #0f172a;
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0;
    }
    tr:last-child td { border-bottom: 0; }
    input[type="text"], input[type="number"], textarea, select {
      width: 100%;
      padding: 8px;
    }
    textarea {
      min-height: 70px;
      resize: vertical;
    }
    input[type="checkbox"] {
      inline-size: 18px;
      block-size: 18px;
      accent-color: var(--accent);
    }
    .name { min-width: 170px; }
    .summary { min-width: 330px; }
    .small { width: 82px; }
    .medium { min-width: 135px; }
    .status {
      min-height: 22px;
      color: var(--muted);
      font-family: "JetBrains Mono", Consolas, monospace;
      font-size: 12px;
    }
    .badge {
      display: inline-block;
      padding: 3px 7px;
      border: 1px solid var(--line);
      border-radius: 999px;
      color: var(--muted);
      font-size: 12px;
      white-space: nowrap;
    }
    .topbar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 18px;
      margin-bottom: 14px;
    }
    @media (max-width: 900px) {
      header, .topbar { align-items: flex-start; flex-direction: column; }
      main { padding: 18px; overflow-x: auto; }
      table { min-width: 1050px; }
    }
  </style>
</head>
<body>
  <header>
    <div>
      <h1>Portfolio Projects</h1>
      <div class="status" id="meta"></div>
    </div>
    <div class="actions">
      <button class="secondary" id="reload">Reload</button>
      <button class="secondary" id="generate">Regenerate README</button>
      <button class="primary" id="save">Save + Regenerate</button>
    </div>
  </header>
  <main>
    <div class="topbar">
      <span class="badge">Profile and CV selection source: data/portfolio-projects.json</span>
      <div class="status" id="status"></div>
    </div>
    <table>
      <thead>
        <tr>
          <th class="small">Order</th>
          <th class="name">Project</th>
          <th class="medium">Focus</th>
          <th class="medium">Status</th>
          <th class="medium">Visibility</th>
          <th class="small">Profile</th>
          <th class="small">CV</th>
          <th class="summary">Summary</th>
        </tr>
      </thead>
      <tbody id="rows"></tbody>
    </table>
  </main>
  <script>
    const statuses = ["ready", "polish", "review", "not-ready"];
    const visibilities = ["featured", "selected", "candidate", "future-featured"];
    let state = null;

    const statusEl = document.querySelector("#status");
    const metaEl = document.querySelector("#meta");
    const rowsEl = document.querySelector("#rows");

    function setStatus(text) {
      statusEl.textContent = text;
    }

    function input(value, key, index, type = "text") {
      const el = document.createElement("input");
      el.type = type;
      el.value = value ?? "";
      el.addEventListener("input", () => {
        state.projects[index][key] = type === "number" ? Number(el.value) : el.value;
      });
      return el;
    }

    function checkbox(value, key, index) {
      const el = document.createElement("input");
      el.type = "checkbox";
      el.checked = Boolean(value);
      el.addEventListener("change", () => {
        state.projects[index][key] = el.checked;
      });
      return el;
    }

    function select(value, key, index, options) {
      const el = document.createElement("select");
      for (const option of options) {
        const child = document.createElement("option");
        child.value = option;
        child.textContent = option;
        child.selected = option === value;
        el.appendChild(child);
      }
      el.addEventListener("change", () => {
        state.projects[index][key] = el.value;
      });
      return el;
    }

    function textarea(value, key, index) {
      const el = document.createElement("textarea");
      el.value = value ?? "";
      el.addEventListener("input", () => {
        state.projects[index][key] = el.value;
      });
      return el;
    }

    function cell(child) {
      const td = document.createElement("td");
      td.appendChild(child);
      return td;
    }

    function render() {
      rowsEl.replaceChildren();
      state.projects
        .map((project, index) => ({ project, index }))
        .sort((a, b) => (a.project.priority ?? 999) - (b.project.priority ?? 999))
        .forEach(({ project, index }) => {
          const tr = document.createElement("tr");
          tr.appendChild(cell(input(project.priority, "priority", index, "number")));
          tr.appendChild(cell(input(project.name, "name", index)));
          tr.appendChild(cell(input(project.focus, "focus", index)));
          tr.appendChild(cell(select(project.status, "status", index, statuses)));
          tr.appendChild(cell(select(project.visibility, "visibility", index, visibilities)));
          tr.appendChild(cell(checkbox(project.show_on_profile, "show_on_profile", index)));
          tr.appendChild(cell(checkbox(project.show_on_cv, "show_on_cv", index)));
          tr.appendChild(cell(textarea(project.summary, "summary", index)));
          rowsEl.appendChild(tr);
        });
      metaEl.textContent = `Updated ${state.updated_at || "unknown"} • ${state.projects.length} projects`;
    }

    async function load() {
      setStatus("Loading...");
      const res = await fetch("/api/projects");
      state = await res.json();
      render();
      setStatus("Ready");
    }

    async function save(regenerate = true) {
      setStatus("Saving...");
      const res = await fetch(`/api/projects?regenerate=${regenerate ? "1" : "0"}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(state)
      });
      const result = await res.json();
      if (!res.ok) {
        setStatus(result.error || "Save failed");
        return;
      }
      state = result.data;
      render();
      setStatus(regenerate ? "Saved and README regenerated" : "Saved");
    }

    async function generate() {
      setStatus("Regenerating README...");
      const res = await fetch("/api/generate", { method: "POST" });
      const result = await res.json();
      setStatus(res.ok ? result.message : result.error);
    }

    document.querySelector("#reload").addEventListener("click", load);
    document.querySelector("#save").addEventListener("click", () => save(true));
    document.querySelector("#generate").addEventListener("click", generate);
    load();
  </script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    def send_json(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/" or self.path == "/dashboard":
            body = HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if self.path == "/api/projects":
            self.send_json(200, json.loads(DATA_PATH.read_text(encoding="utf-8")))
            return

        self.send_json(404, {"error": "Not found"})

    def do_HEAD(self):
        if self.path == "/" or self.path == "/dashboard":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            return
        if self.path == "/api/projects":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            return
        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        if self.path.startswith("/api/projects"):
            try:
                length = int(self.headers.get("Content-Length", "0"))
                payload = json.loads(self.rfile.read(length))
                payload["updated_at"] = datetime.now(timezone.utc).date().isoformat()
                DATA_PATH.write_text(
                    json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8",
                )
                if "regenerate=1" in self.path:
                    subprocess.run(["python3", str(GENERATOR)], check=True, cwd=ROOT)
                self.send_json(200, {"message": "Saved", "data": payload})
            except Exception as error:
                self.send_json(500, {"error": str(error)})
            return

        if self.path == "/api/generate":
            try:
                subprocess.run(["python3", str(GENERATOR)], check=True, cwd=ROOT)
                self.send_json(200, {"message": "README regenerated"})
            except Exception as error:
                self.send_json(500, {"error": str(error)})
            return

        self.send_json(404, {"error": "Not found"})

    def log_message(self, fmt, *args):
        print("%s - %s" % (self.address_string(), fmt % args))


def main():
    server = ThreadingHTTPServer(("127.0.0.1", 8765), Handler)
    print("Portfolio dashboard: http://127.0.0.1:8765")
    server.serve_forever()


if __name__ == "__main__":
    main()
