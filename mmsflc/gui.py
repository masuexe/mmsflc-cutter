"""Local window: pick a recording, list its matches, export them.

Tk on this machine has no Chinese font, so the window is a page served on
localhost and opened in the browser.
"""

from __future__ import annotations

import json
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from mmsflc.cut import cut_match
from mmsflc.find import cache_dir, find_matches
from mmsflc.segment import Match

HOST = "127.0.0.1"
PORT = 8765
VIDEO_SUFFIXES = {".mp4", ".mkv", ".webm", ".mpd", ".mov"}
_jobs: dict[str, dict] = {}
_jobs_lock = threading.Lock()


def recording_path(text: str) -> Path:
    raw = text.strip().strip('"')
    if len(raw) >= 2 and raw[1] == ":" and raw[0].isalpha():
        rest = raw[2:].replace("\\", "/").lstrip("/")
        return Path(f"/mnt/{raw[0].lower()}") / rest
    return Path(raw)


def clock(seconds: float) -> str:
    total = int(round(seconds))
    return f"{total // 3600:d}:{total % 3600 // 60:02d}:{total % 60:02d}"


def generation(game: int | None) -> str:
    return f"{game}代" if game else "未知"


def list_dir(path: Path) -> dict:
    path = path.expanduser().resolve()
    selected = None
    if path.is_file():
        selected = path
        path = path.parent
    if not path.is_dir():
        raise FileNotFoundError(path)
    entries = []
    for child in sorted(path.iterdir(), key=lambda item: (not item.is_dir(), item.name.lower())):
        if child.name.startswith("."):
            continue
        entries.append(
            {
                "name": child.name,
                "path": str(child),
                "dir": child.is_dir(),
                "video": child.suffix.lower() in VIDEO_SUFFIXES,
            }
        )
    parent = None if path.parent == path else str(path.parent)
    return {
        "path": str(path),
        "parent": parent,
        "selected": str(selected) if selected else None,
        "entries": entries,
    }


def match_rows(found: list[Match]) -> list[dict]:
    rows = []
    for index, match in enumerate(found, start=1):
        rows.append(
            {
                "index": f"{index:02d}",
                "game": generation(match.game),
                "start": clock(match.start),
                "end": clock(match.end),
                "length": f"{match.end - match.start:.0f}秒",
            }
        )
    return rows


def _job_snapshot(job: dict) -> dict:
    with _jobs_lock:
        return {
            "status": job["status"],
            "done": job["done"],
            "error": job["error"],
            "matches": job["matches"],
        }


def _set_job(job: dict, **fields: object) -> None:
    with _jobs_lock:
        job.update(fields)


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._bytes(200, PAGE.encode(), "text/html; charset=utf-8")
            return
        if parsed.path == "/api/list":
            query = parse_qs(parsed.query)
            raw = query.get("path", ["/mnt/d/video"])[0]
            try:
                self._json(list_dir(recording_path(raw)))
            except FileNotFoundError:
                self._json({"error": "找不到目录"}, status=404)
            return
        if parsed.path == "/api/job":
            job_id = parse_qs(parsed.query).get("id", [""])[0]
            job = _jobs.get(job_id)
            if job is None:
                self._json({"error": "没有这个任务"}, status=404)
                return
            self._json(_job_snapshot(job))
            return
        self._json({"error": "没有这个页面"}, status=404)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))) or b"{}")
        except json.JSONDecodeError:
            self._json({"error": "请求不是 JSON"}, status=400)
            return
        if parsed.path == "/api/scan":
            self._start_scan(str(body.get("path", "")))
            return
        if parsed.path == "/api/export":
            self._start_export(str(body.get("path", "")), str(body.get("dest", "")))
            return
        self._json({"error": "没有这个页面"}, status=404)

    def _start_scan(self, raw: str) -> None:
        recording = recording_path(raw)
        if not recording.is_file():
            self._json({"error": "找不到录像"}, status=400)
            return
        job = {"status": "正在识别…", "done": False, "error": None, "matches": None}
        job_id = _store_job(job)
        threading.Thread(target=_scan, args=(job, recording), daemon=True).start()
        self._json({"id": job_id})

    def _start_export(self, raw: str, dest_raw: str) -> None:
        recording = recording_path(raw)
        dest = recording_path(dest_raw)
        if not recording.is_file():
            self._json({"error": "找不到录像"}, status=400)
            return
        if not dest_raw.strip():
            self._json({"error": "先选择输出目录"}, status=400)
            return
        job = {"status": "正在导出…", "done": False, "error": None, "matches": None}
        job_id = _store_job(job)
        threading.Thread(target=_export, args=(job, recording, dest), daemon=True).start()
        self._json({"id": job_id})

    def _json(self, payload: dict, status: int = 200) -> None:
        self._bytes(status, json.dumps(payload, ensure_ascii=False).encode(), "application/json; charset=utf-8")

    def _bytes(self, status: int, data: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt: str, *args: object) -> None:
        return


def _store_job(job: dict) -> str:
    job_id = str(len(_jobs) + 1)
    _jobs[job_id] = job
    return job_id


def _scan(job: dict, recording: Path) -> None:
    try:
        found = find_matches(recording, cache_dir(recording), log=lambda message: _set_job(job, status=message))
        rows = match_rows(found)
        status = f"认出 {len(found)} 局" if found else "没有对局"
        _set_job(job, status=status, matches=rows, done=True)
    except Exception as exc:
        _set_job(job, status=f"识别失败: {exc}", error=str(exc), done=True)


def _export(job: dict, recording: Path, dest: Path) -> None:
    try:
        found = find_matches(recording, cache_dir(recording), log=lambda message: _set_job(job, status=message))
        if not found:
            _set_job(job, status="没有对局", matches=[], done=True)
            return
        for index, match in enumerate(found, start=1):
            game = match.game if match.game else 0
            _set_job(job, status=f"正在导出 {index:02d}_sf{game}.mp4")
            cut_match(recording, match, dest, index)
        _set_job(job, status=f"已导出 {len(found)} 个文件到 {dest}", matches=match_rows(found), done=True)
    except Exception as exc:
        _set_job(job, status=f"导出失败: {exc}", error=str(exc), done=True)


PAGE = """<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<title>流星洛克人切局</title>
<style>
  :root { color-scheme: light; font-family: "Noto Sans CJK SC", "Microsoft YaHei", "WenQuanYi Zen Hei", sans-serif; }
  html, body { background: #fff; color: #1c1c1c; }
  body { margin: 24px auto; max-width: 920px; }
  h1 { font-size: 22px; font-weight: 650; margin: 0 0 16px; }
  section { margin: 0 0 18px; }
  h2 { font-size: 14px; margin: 0 0 8px; color: #444; }
  .row { display: flex; gap: 8px; align-items: center; margin-bottom: 8px; }
  input[type=text] { flex: 1; padding: 6px 8px; border: 1px solid #ccc; border-radius: 4px; background: #fff; color: #1c1c1c; }
  button { padding: 6px 12px; border: 1px solid #888; border-radius: 4px; background: #f4f4f4; cursor: pointer; }
  button:disabled { opacity: 0.5; cursor: default; }
  button.primary { background: #1d4e89; color: white; border-color: #1d4e89; }
  .list { border: 1px solid #ddd; border-radius: 4px; max-height: 180px; overflow: auto; }
  .list button { display: block; width: 100%; text-align: left; border: 0; border-bottom: 1px solid #eee; border-radius: 0; background: white; }
  .list button.dir { color: #1d4e89; }
  .list button.on { background: #e7f0fa; }
  table { width: 100%; border-collapse: collapse; }
  th, td { padding: 6px 8px; border-bottom: 1px solid #eee; text-align: center; background: #fff; }
  th { background: #f6f6f6; font-weight: 650; }
  #status { min-height: 1.4em; color: #333; }
</style>
</head>
<body>
<h1>流星洛克人切局</h1>
<section>
  <h2>录像</h2>
  <div class="row">
    <input id="rec" type="text" placeholder="选择下面的文件，或粘贴路径">
    <button id="rec-use" type="button">使用路径</button>
    <button id="scan" class="primary" type="button">识别</button>
  </div>
  <div id="rec-list" class="list"></div>
</section>
<section>
  <h2>对局</h2>
  <table>
    <thead><tr><th>序号</th><th>代</th><th>开始</th><th>结束</th><th>时长</th></tr></thead>
    <tbody id="matches"></tbody>
  </table>
</section>
<section>
  <h2>输出目录</h2>
  <div class="row">
    <input id="dest" type="text" placeholder="选择下面的目录，或粘贴路径">
    <button id="dest-use" type="button">使用路径</button>
    <button id="export" class="primary" type="button">导出</button>
  </div>
  <div id="dest-list" class="list"></div>
</section>
<p id="status">选择一条录像</p>
<script>
const recInput = document.querySelector("#rec");
const destInput = document.querySelector("#dest");
const statusLine = document.querySelector("#status");
let busy = false;

function setBusy(next) {
  busy = next;
  for (const id of ["scan", "export", "rec-use", "dest-use"]) {
    document.querySelector("#" + id).disabled = next;
  }
}

async function loadList(el, path, onFile, onDir) {
  const response = await fetch("/api/list?path=" + encodeURIComponent(path));
  const data = await response.json();
  if (!response.ok) {
    statusLine.textContent = data.error || "找不到目录";
    return;
  }
  if (onDir) onDir(data.path);
  if (data.selected && el.id === "rec-list") recInput.value = data.selected;
  el.replaceChildren();
  if (data.parent) {
    const up = document.createElement("button");
    up.type = "button";
    up.className = "dir";
    up.textContent = "上一级";
    up.addEventListener("click", () => loadList(el, data.parent, onFile, onDir));
    el.append(up);
  }
  for (const entry of data.entries) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = entry.dir ? "dir" : "";
    button.textContent = entry.dir ? entry.name + "/" : entry.name;
    button.addEventListener("click", () => {
      if (entry.dir) loadList(el, entry.path, onFile, onDir);
      else if (onFile) onFile(entry);
    });
    el.append(button);
  }
}

function showMatches(rows) {
  const body = document.querySelector("#matches");
  body.replaceChildren();
  for (const row of rows || []) {
    const tr = document.createElement("tr");
    for (const key of ["index", "game", "start", "end", "length"]) {
      const td = document.createElement("td");
      td.textContent = row[key];
      tr.append(td);
    }
    body.append(tr);
  }
}

async function watch(id) {
  setBusy(true);
  try {
    for (;;) {
      const response = await fetch("/api/job?id=" + encodeURIComponent(id));
      const job = await response.json();
      statusLine.textContent = job.status || "";
      if (job.matches) showMatches(job.matches);
      if (job.done) return;
      await new Promise((resolve) => setTimeout(resolve, 400));
    }
  } finally {
    setBusy(false);
  }
}

async function post(url, payload) {
  const response = await fetch(url, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(payload),
  });
  const data = await response.json();
  if (!response.ok) {
    statusLine.textContent = data.error || "失败";
    return;
  }
  await watch(data.id);
}

document.querySelector("#scan").addEventListener("click", () => {
  if (!busy) post("/api/scan", {path: recInput.value});
});
document.querySelector("#export").addEventListener("click", () => {
  if (!busy) post("/api/export", {path: recInput.value, dest: destInput.value});
});
document.querySelector("#rec-use").addEventListener("click", () => {
  if (recInput.value.trim()) loadList(document.querySelector("#rec-list"), recInput.value.trim(), pickVideo, null);
});
document.querySelector("#dest-use").addEventListener("click", () => {
  if (destInput.value.trim()) loadList(document.querySelector("#dest-list"), destInput.value.trim(), null, pickDir);
});

function pickVideo(entry) {
  if (!entry.video) {
    statusLine.textContent = "这不是录像文件";
    return;
  }
  recInput.value = entry.path;
  statusLine.textContent = entry.name;
}
function pickDir(path) {
  destInput.value = path;
}

loadList(document.querySelector("#rec-list"), "/mnt/d/BaiduNetdiskDownload", pickVideo, null);
loadList(document.querySelector("#dest-list"), "/mnt/d/video", null, pickDir);
</script>
</body>
</html>
"""


def run() -> None:
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    url = f"http://{HOST}:{PORT}/"
    print(url, flush=True)
    webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()
