"""Dependency-free local web UI for financial analysis tasks."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
from pathlib import Path
from threading import Lock, Thread
import traceback
from typing import Any, Callable
from urllib.parse import urlparse
import uuid

from ..application.app import FinancialAnalysisApp
from ..data_access.statement_repository import JSONStatementDirectoryRepository, SchemaCatalog
from ..domain.statement_bundle import StatementQuery
from ..runtime import create_run_directory


PAGE = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Financial Analysis Workspace</title>
  <style>
    :root { --ink:#17233b; --muted:#64748b; --line:#d9e2ee; --paper:#fff; --blue:#2354d4; --teal:#0f897c; --bg:#edf2f7; --danger:#b42318; }
    * { box-sizing:border-box; }
    body { margin:0; color:var(--ink); background:linear-gradient(145deg,#e9f0fb,#f5f7fa 50%,#e7f4f1); font:15px/1.5 system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; min-height:100vh; }
    .shell { max-width:1120px; margin:0 auto; padding:48px 24px 72px; }
    header { display:flex; justify-content:space-between; gap:32px; align-items:flex-end; margin-bottom:26px; }
    .eyebrow { color:var(--blue); font-size:12px; font-weight:800; letter-spacing:.16em; text-transform:uppercase; }
    h1 { font:700 clamp(30px,5vw,52px)/1.05 Georgia,serif; letter-spacing:-.03em; margin:8px 0 10px; }
    header p { max-width:700px; color:var(--muted); margin:0; }
    .badge { white-space:nowrap; padding:8px 12px; border:1px solid #a9c4bc; border-radius:99px; color:#11675e; background:#f3fffb; font-weight:700; }
    .grid { display:grid; grid-template-columns:minmax(0,1.35fr) minmax(300px,.65fr); gap:22px; align-items:start; }
    .card { background:rgba(255,255,255,.94); border:1px solid rgba(190,204,222,.9); border-radius:18px; box-shadow:0 18px 45px rgba(51,65,85,.10); overflow:hidden; }
    .card-head { padding:22px 24px 16px; border-bottom:1px solid var(--line); }
    .card-head h2 { margin:0 0 3px; font-size:18px; }
    .card-head p { margin:0; color:var(--muted); font-size:13px; }
    form { padding:22px 24px 24px; }
    .fields { display:grid; grid-template-columns:1fr 1fr; gap:16px; }
    .wide { grid-column:1/-1; }
    label { display:block; font-weight:700; font-size:13px; margin-bottom:6px; }
    input,select { width:100%; border:1px solid #c4cfdd; border-radius:10px; padding:11px 12px; color:var(--ink); background:#fff; font:inherit; outline:none; }
    input:focus,select:focus { border-color:var(--blue); box-shadow:0 0 0 3px rgba(35,84,212,.12); }
    .hint { color:var(--muted); font-size:12px; margin-top:5px; }
    button { width:100%; border:0; border-radius:11px; margin-top:22px; padding:13px 18px; color:#fff; background:linear-gradient(100deg,var(--blue),#3d69df); font-weight:800; font-size:15px; cursor:pointer; }
    button:hover { filter:brightness(1.05); }
    button:disabled { cursor:wait; opacity:.65; }
    .tasks { padding:8px 18px 18px; max-height:650px; overflow:auto; }
    .empty { color:var(--muted); padding:22px 6px; text-align:center; }
    .task { padding:16px 6px; border-bottom:1px solid var(--line); }
    .task:last-child { border-bottom:0; }
    .task-top { display:flex; align-items:center; justify-content:space-between; gap:12px; }
    .task-title { font-weight:800; }
    .status { border-radius:99px; padding:4px 8px; font-size:11px; font-weight:800; text-transform:uppercase; letter-spacing:.05em; background:#edf2f7; }
    .status.succeeded { background:#dcfce7; color:#166534; }
    .status.failed { background:#fee2e2; color:var(--danger); }
    .status.running { background:#dbeafe; color:#1d4ed8; }
    .task-meta,.task-message { color:var(--muted); font-size:12px; margin-top:6px; overflow-wrap:anywhere; }
    .task-message.error { color:var(--danger); }
    .artifacts { display:flex; flex-wrap:wrap; gap:6px; margin-top:9px; }
    .artifacts a { color:var(--blue); background:#eef3ff; padding:5px 8px; border-radius:7px; text-decoration:none; font-size:12px; font-weight:700; }
    @media (max-width:820px) { .grid { grid-template-columns:1fr; } header { display:block; } .badge { display:inline-block; margin-top:18px; } }
    @media (max-width:560px) { .fields { grid-template-columns:1fr; } .wide { grid-column:auto; } .shell { padding:28px 14px 48px; } }
  </style>
</head>
<body>
<main class="shell">
  <header>
    <div><div class="eyebrow">Asset Report · Local Workspace</div><h1>Financial analysis, on demand.</h1><p>Retrieve balance sheet, income statement, and cash-flow data for an inclusive time frame; normalize it to CAS, IFRS-EU, or US-GAAP; and generate analysis artifacts locally.</p></div>
    <div class="badge">Dependency-free · Local only</div>
  </header>
  <div class="grid">
    <section class="card">
      <div class="card-head"><h2>Start an analysis task</h2><p>Every run receives its own timestamped directory below the selected output folder.</p></div>
      <form id="task-form">
        <div class="fields">
          <div class="wide"><label for="action">Task</label><select id="action" name="action"><option value="full_analysis">Normalize all three statements + financial-position report</option><option value="normalize_statements">Normalize all three statements</option><option value="financial_position_report">Generate financial-position report</option></select></div>
          <div class="wide"><label for="company">Company</label><input id="company" name="company" value="Gotion High-Tech Co., Ltd." required></div>
          <div><label for="start_period">Start period</label><input id="start_period" name="start_period" value="2024" pattern="[0-9]{4}(Q[1-4])?" required></div>
          <div><label for="end_period">End period</label><input id="end_period" name="end_period" value="2025" pattern="[0-9]{4}(Q[1-4])?" required></div>
          <div class="wide"><label for="schema_profile">Accounting schema</label><select id="schema_profile" name="schema_profile"></select></div>
          <div class="wide"><label for="source_directory">Statement data directory</label><input id="source_directory" name="source_directory" required><div class="hint">JSON files may be nested; company, period, profile, and statement type are read from each file.</div></div>
          <div class="wide"><label for="output_directory">Output directory</label><input id="output_directory" name="output_directory" required></div>
        </div>
        <button id="submit" type="submit">Start analysis</button>
      </form>
    </section>
    <aside class="card">
      <div class="card-head"><h2>Recent tasks</h2><p>Status and downloadable artifacts update automatically.</p></div>
      <div id="tasks" class="tasks"><div class="empty">No tasks started yet.</div></div>
    </aside>
  </div>
</main>
<script>
const form=document.querySelector('#task-form'), tasksNode=document.querySelector('#tasks'), submit=document.querySelector('#submit');
const labels={full_analysis:'Full analysis',normalize_statements:'Normalize statements',financial_position_report:'Position report'};
const escapeHtml=value=>String(value??'').replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
async function loadConfig(){const response=await fetch('/api/config');const config=await response.json();document.querySelector('#source_directory').value=config.default_source_directory;document.querySelector('#output_directory').value=config.default_output_directory;const select=document.querySelector('#schema_profile');select.innerHTML=config.profiles.map(p=>`<option value="${escapeHtml(p.profile)}">${escapeHtml(p.profile)} · ${escapeHtml(p.standard)}</option>`).join('');}
async function refresh(){const response=await fetch('/api/tasks');const data=await response.json();if(!data.tasks.length){tasksNode.innerHTML='<div class="empty">No tasks started yet.</div>';return;}tasksNode.innerHTML=data.tasks.map(task=>{const links=(task.artifacts||[]).map((item,index)=>`<a href="/api/tasks/${task.id}/artifacts/${index}" target="_blank">${escapeHtml(item.name)}</a>`).join('');return `<article class="task"><div class="task-top"><div class="task-title">${escapeHtml(labels[task.action]||task.action)}</div><span class="status ${escapeHtml(task.status)}">${escapeHtml(task.status)}</span></div><div class="task-meta">${escapeHtml(task.company)} · ${escapeHtml(task.start_period)}–${escapeHtml(task.end_period)} · ${escapeHtml(task.schema_profile)}</div>${task.message?`<div class="task-message ${task.status==='failed'?'error':''}">${escapeHtml(task.message)}</div>`:''}${links?`<div class="artifacts">${links}</div>`:''}</article>`;}).join('');}
form.addEventListener('submit',async event=>{event.preventDefault();submit.disabled=true;submit.textContent='Starting…';const payload=Object.fromEntries(new FormData(form).entries());try{const response=await fetch('/api/tasks',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});const data=await response.json();if(!response.ok)throw new Error(data.error||'Could not start task');await refresh();}catch(error){alert(error.message);}finally{submit.disabled=false;submit.textContent='Start analysis';}});
loadConfig().then(refresh);setInterval(refresh,1500);
</script>
</body>
</html>"""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class AnalysisTask:
    id: str
    action: str
    company: str
    start_period: str
    end_period: str
    schema_profile: str
    source_directory: str
    output_directory: str
    status: str = "queued"
    message: str = "Waiting to start"
    created_at: str = field(default_factory=_utc_now)
    updated_at: str = field(default_factory=_utc_now)
    artifacts: list[Path] = field(default_factory=list)

    def as_json(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "action": self.action,
            "company": self.company,
            "start_period": self.start_period,
            "end_period": self.end_period,
            "schema_profile": self.schema_profile,
            "source_directory": self.source_directory,
            "output_directory": self.output_directory,
            "status": self.status,
            "message": self.message,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "artifacts": [
                {"name": path.name, "path": str(path)} for path in self.artifacts
            ],
        }


class AnalysisTaskManager:
    ACTIONS = {"normalize_statements", "financial_position_report", "full_analysis"}

    def __init__(self) -> None:
        self._tasks: dict[str, AnalysisTask] = {}
        self._lock = Lock()

    def submit(self, payload: dict[str, Any]) -> AnalysisTask:
        action = str(payload.get("action", ""))
        if action not in self.ACTIONS:
            raise ValueError("Select a supported analysis task")
        required = (
            "company",
            "start_period",
            "end_period",
            "schema_profile",
            "source_directory",
            "output_directory",
        )
        values = {name: str(payload.get(name, "")).strip() for name in required}
        missing = [name for name, value in values.items() if not value]
        if missing:
            raise ValueError("Missing required field(s): " + ", ".join(missing))
        StatementQuery(
            company=values["company"],
            start_period=values["start_period"],
            end_period=values["end_period"],
            schema_profile=values["schema_profile"],
        )
        SchemaCatalog().profile(values["schema_profile"])
        task = AnalysisTask(id=uuid.uuid4().hex[:12], action=action, **values)
        with self._lock:
            self._tasks[task.id] = task
        Thread(target=self._run, args=(task.id,), daemon=True).start()
        return task

    def list(self) -> list[AnalysisTask]:
        with self._lock:
            return sorted(
                self._tasks.values(), key=lambda task: task.created_at, reverse=True
            )

    def get(self, task_id: str) -> AnalysisTask | None:
        with self._lock:
            return self._tasks.get(task_id)

    def _update(self, task_id: str, **changes: Any) -> None:
        with self._lock:
            task = self._tasks[task_id]
            for name, value in changes.items():
                setattr(task, name, value)
            task.updated_at = _utc_now()

    def _run(self, task_id: str) -> None:
        task = self.get(task_id)
        if task is None:
            return
        self._update(task_id, status="running", message="Retrieving statement data")
        try:
            run_directory = create_run_directory(task.output_directory, "analysis")
            query = StatementQuery(
                company=task.company,
                start_period=task.start_period,
                end_period=task.end_period,
                schema_profile=task.schema_profile,
            )
            artifacts: list[Path] = []
            app = FinancialAnalysisApp()
            if task.action in {"normalize_statements", "full_analysis"}:
                result = app.retrieve_three_statements(
                    task.source_directory,
                    run_directory,
                    company=task.company,
                    start_period=task.start_period,
                    end_period=task.end_period,
                    schema_profile=task.schema_profile,
                )
                artifacts.extend([result.manifest_path, *result.statement_paths])

            if task.action in {"financial_position_report", "full_analysis"}:
                repository = JSONStatementDirectoryRepository(task.source_directory)
                balance_paths = repository.find_balance_sheet_paths(query)
                report_path = run_directory / "financial-position-report.html"
                app.generate_time_frame_report(
                    balance_paths,
                    report_path,
                    title=(
                        f"{task.company} {task.start_period}–{task.end_period} "
                        "Financial Position"
                    ),
                )
                artifacts.insert(0, report_path)

            message = f"Completed with {len(artifacts)} artifact(s) in {run_directory}"
            self._update(
                task_id,
                status="succeeded",
                message=message,
                artifacts=artifacts,
            )
        except Exception as exc:  # the UI records task failures instead of stopping the server
            traceback.print_exc()
            self._update(task_id, status="failed", message=str(exc), artifacts=[])


def make_handler(
    manager: AnalysisTaskManager,
    project_root: Path,
) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "AssetReportUI/5.0"

        def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
            path = urlparse(self.path).path
            if path == "/":
                self._send_bytes(PAGE.encode("utf-8"), "text/html; charset=utf-8")
                return
            if path == "/api/config":
                catalog = SchemaCatalog()
                self._send_json(
                    {
                        "profiles": [
                            {
                                "profile": profile["profile"],
                                "standard": profile["standard"],
                                "jurisdiction": profile["jurisdiction"],
                            }
                            for profile in catalog.profiles
                        ],
                        "default_source_directory": str(
                            project_root / "sample_data"
                        ),
                        "default_output_directory": str(project_root / "output"),
                    }
                )
                return
            if path == "/api/tasks":
                self._send_json({"tasks": [task.as_json() for task in manager.list()]})
                return

            parts = path.strip("/").split("/")
            if len(parts) == 3 and parts[:2] == ["api", "tasks"]:
                task = manager.get(parts[2])
                if task is None:
                    self._send_json({"error": "Task not found"}, HTTPStatus.NOT_FOUND)
                else:
                    self._send_json(task.as_json())
                return
            if (
                len(parts) == 5
                and parts[:2] == ["api", "tasks"]
                and parts[3] == "artifacts"
            ):
                task = manager.get(parts[2])
                try:
                    index = int(parts[4])
                    artifact = task.artifacts[index] if task is not None else None
                except (ValueError, IndexError):
                    artifact = None
                if artifact is None or not artifact.is_file():
                    self._send_json({"error": "Artifact not found"}, HTTPStatus.NOT_FOUND)
                    return
                media_type = mimetypes.guess_type(artifact.name)[0] or "application/octet-stream"
                self._send_bytes(
                    artifact.read_bytes(),
                    media_type,
                    {"Content-Disposition": f'inline; filename="{artifact.name}"'},
                )
                return
            self._send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)

        def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
            if urlparse(self.path).path != "/api/tasks":
                self._send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length <= 0 or length > 1_000_000:
                    raise ValueError("Request body must be between 1 byte and 1 MB")
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
                if not isinstance(payload, dict):
                    raise ValueError("Request body must be a JSON object")
                task = manager.submit(payload)
            except (ValueError, json.JSONDecodeError) as exc:
                self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
                return
            self._send_json(task.as_json(), HTTPStatus.ACCEPTED)

        def log_message(self, format: str, *args: object) -> None:
            return

        def _send_json(
            self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK
        ) -> None:
            self._send_bytes(
                (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8"),
                "application/json; charset=utf-8",
                status=status,
            )

        def _send_bytes(
            self,
            content: bytes,
            content_type: str,
            headers: dict[str, str] | None = None,
            status: HTTPStatus = HTTPStatus.OK,
        ) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-store")
            for name, value in (headers or {}).items():
                self.send_header(name, value)
            self.end_headers()
            self.wfile.write(content)

    return Handler


def create_server(
    host: str = "127.0.0.1",
    port: int = 8765,
    *,
    manager: AnalysisTaskManager | None = None,
    project_root: str | Path | None = None,
) -> ThreadingHTTPServer:
    root = Path(project_root or Path(__file__).resolve().parents[2]).resolve()
    task_manager = manager or AnalysisTaskManager()
    return ThreadingHTTPServer((host, port), make_handler(task_manager, root))


def serve(host: str = "127.0.0.1", port: int = 8765) -> None:
    server = create_server(host, port)
    print(f"Financial Analysis UI: http://{host}:{server.server_address[1]}/")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
