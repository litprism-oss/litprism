#!/usr/bin/env python3
"""End-to-end smoke test for a deployed LitPrism API.

    python smoke_test.py https://<api-host> [--token <supabase access token>]

Covers the real production path, not mocks:
  1. API is up (/openapi.json)
  2. Upload flow: create project -> upload a 3-article RIS file -> set criteria ->
     run abstract screening with the configured LLM -> read the results
  3. Search flow: create project -> PubMed/Europe PMC/Semantic Scholar search ->
     articles arrive, and the WebSocket delivers progress events
  4. Clean up: deletes ONLY the projects this script created (names start with SMOKE_PREFIX)

Standard library only, except `websockets` (pip install websockets), used for step 3.
Exit code 0 = everything passed, 1 = a check failed.
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid

SMOKE_PREFIX = "SMOKE TEST (auto, safe to delete)"
SCREEN_TIMEOUT = 240
SEARCH_TIMEOUT = 240

RIS = """TY  - JOUR
TI  - Large language models for title and abstract screening in systematic reviews
AB  - We evaluated whether a large language model can automate the screening of titles and abstracts for systematic reviews. Across three review datasets the model reached high sensitivity while reducing reviewer workload.
AU  - Doe, Jane
PY  - 2024
JO  - Journal of Smoke Tests
DO  - 10.0000/smoke.1
ER  -

TY  - JOUR
TI  - Effect of vitamin D supplementation on bone mineral density in postmenopausal women
AB  - In this randomised trial of 400 postmenopausal women we compared vitamin D supplementation with placebo over 24 months and measured bone mineral density at the lumbar spine and hip.
AU  - Roe, Richard
PY  - 2022
JO  - Journal of Smoke Tests
DO  - 10.0000/smoke.2
ER  -

TY  - JOUR
TI  - Active learning for prioritising records during systematic review screening
AB  - Active learning ranks unscreened records by predicted relevance so reviewers see likely includes first. We describe a screening prioritisation tool for systematic reviews and report work saved over sampling.
AU  - Poe, Pat
PY  - 2023
JO  - Journal of Smoke Tests
DO  - 10.0000/smoke.3
ER  -
"""

failures: list[str] = []
created_projects: list[str] = []


def log(msg: str) -> None:
    print(msg, flush=True)


def check(ok: bool, label: str, detail: str = "") -> bool:
    log(f"  {'PASS' if ok else 'FAIL'}  {label}" + (f"  ({detail})" if detail else ""))
    if not ok:
        failures.append(label)
    return ok


class Api:
    def __init__(self, base: str, token: str | None) -> None:
        self.base = base.rstrip("/")
        self.token = token

    def _headers(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        headers = {"Accept": "application/json", "User-Agent": "litprism-smoke-test"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        headers.update(extra or {})
        return headers

    def request(
        self, method: str, path: str, body: object | None = None, raw: bytes | None = None,
        content_type: str | None = None, timeout: int = 60,
    ) -> tuple[int, object]:
        data = raw
        headers = self._headers()
        if body is not None:
            data = json.dumps(body).encode()
            headers["Content-Type"] = "application/json"
        if content_type:
            headers["Content-Type"] = content_type
        req = urllib.request.Request(self.base + path, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                text = resp.read().decode() or "null"
                return resp.status, json.loads(text)
        except urllib.error.HTTPError as exc:
            text = exc.read().decode()
            try:
                return exc.code, json.loads(text)
            except ValueError:
                return exc.code, text

    def upload(self, project_id: str, filename: str, content: str) -> tuple[int, object]:
        boundary = uuid.uuid4().hex
        payload = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
            "Content-Type: application/x-research-info-systems\r\n\r\n"
            f"{content}\r\n--{boundary}--\r\n"
        ).encode()
        return self.request(
            "POST", f"/projects/{project_id}/upload", raw=payload,
            content_type=f"multipart/form-data; boundary={boundary}",
        )


def new_project(api: Api, label: str) -> str | None:
    name = f"{SMOKE_PREFIX} {label} {time.strftime('%Y-%m-%d %H:%M:%S')}"
    status, body = api.request(
        "POST", "/projects", {"name": name, "review_type": "systematic",
                              "research_question": "Automating abstract screening"},
    )
    if not check(status == 201 and isinstance(body, dict), f"create project ({label})", f"HTTP {status}"):
        return None
    created_projects.append(body["id"])
    return body["id"]


def poll(api: Api, path: str, timeout: int, done) -> dict | None:
    deadline = time.time() + timeout
    last: dict | None = None
    while time.time() < deadline:
        status, body = api.request("GET", path)
        if status == 200 and isinstance(body, dict):
            last = body
            if done(body):
                return body
        time.sleep(4)
    return last


def upload_and_screen(api: Api) -> None:
    log("\n[2] Upload + screening (uses the deployed LLM)")
    pid = new_project(api, "upload")
    if not pid:
        return

    status, body = api.upload(pid, "smoke.ris", RIS)
    ok = status == 201 and isinstance(body, dict) and body.get("new_articles") == 3
    if not check(ok, "upload RIS with 3 articles", f"HTTP {status}, {body if not ok else 'new_articles=3'}"):
        return

    status, body = api.request(
        "POST", f"/projects/{pid}/criteria",
        {"inclusion": ["Studies about automating title and abstract screening for systematic reviews"],
         "exclusion": ["Studies not related to systematic reviews or evidence synthesis"]},
    )
    if not check(status == 201, "save criteria", f"HTTP {status}"):
        return

    status, body = api.request("POST", f"/projects/{pid}/screening/run", {"stage": "abstract"})
    if not check(status == 202 and isinstance(body, dict), "start screening run", f"HTTP {status} {body if status != 202 else ''}"):
        return
    run_id = body["id"]

    terminal = {"completed", "failed", "cancelled", "error"}
    run = poll(api, f"/projects/{pid}/screening/runs/{run_id}", SCREEN_TIMEOUT,
               lambda r: r.get("status") in terminal)
    if not run:
        check(False, "screening run finished", "no response")
        return
    check(run.get("status") == "completed", "screening run completed",
          f"status={run.get('status')} screened={run.get('screened_count')}/{run.get('total_articles')} errors={run.get('error_count')}")
    check(run.get("error_count") == 0, "no per-article LLM errors", f"error_count={run.get('error_count')}")

    status, body = api.request("GET", f"/projects/{pid}/screening/results?run_id={run_id}")
    items = body.get("items", []) if status == 200 and isinstance(body, dict) else []
    check(len(items) == 3 and all(i.get("screening_result") for i in items),
          "results returned for all 3 articles", f"HTTP {status}, {len(items)} items")
    for item in items:
        res = item.get("screening_result") or {}
        log(f"        {res.get('decision', '?'):9} {res.get('confidence', 0):.2f}  {item.get('title', '')[:70]}")
    vitd = [i for i in items if "vitamin d" in i.get("title", "").lower()]
    if vitd and vitd[0].get("screening_result"):
        check(vitd[0]["screening_result"]["decision"] != "include",
              "off-topic article (vitamin D) is not included")


def search_and_progress(api: Api, ws_base: str) -> None:
    log("\n[3] Search + WebSocket progress")
    pid = new_project(api, "search")
    if not pid:
        return

    events: list[dict] = []
    ws_state = {"connected": False, "error": ""}
    stop = threading.Event()

    def listen() -> None:
        try:
            from websockets.sync.client import connect  # type: ignore[import-not-found]
        except ImportError:
            ws_state["error"] = "websockets not installed"
            return
        try:
            with connect(f"{ws_base}/ws/{pid}", open_timeout=20, user_agent_header="litprism-smoke-test") as ws:
                if api.token:
                    ws.send(json.dumps({"token": api.token}))
                ws_state["connected"] = True
                while not stop.is_set():
                    try:
                        msg = ws.recv(timeout=2)
                    except TimeoutError:
                        continue
                    try:
                        events.append(json.loads(msg))
                    except ValueError:
                        pass
                    if events and events[-1].get("event") in {"search_complete", "search_error"}:
                        return
        except Exception as exc:  # noqa: BLE001 - report, don't crash the run
            ws_state["error"] = f"{type(exc).__name__}: {exc}"

    thread = threading.Thread(target=listen, daemon=True)
    thread.start()
    time.sleep(3)  # let the socket connect before the search starts

    status, body = api.request(
        "POST", f"/projects/{pid}/search-runs",
        {"review_type": "systematic",
         "query_final": '"large language model"[tiab] AND "systematic review"[tiab] AND screening[tiab]',
         "filters": None},
    )
    if not check(status == 201 and isinstance(body, dict), "create search run", f"HTTP {status}"):
        stop.set()
        return
    run_id = body["id"]
    status, body = api.request("POST", f"/projects/{pid}/search-runs/{run_id}/execute")
    if not check(status == 202, "execute search run", f"HTTP {status}"):
        stop.set()
        return

    run = poll(api, f"/projects/{pid}/search-runs/{run_id}", SEARCH_TIMEOUT,
               lambda r: r.get("status") not in {"draft", "locked", "running", "pending"})
    stop.set()
    thread.join(timeout=10)
    check(bool(run) and run.get("status") == "completed", "search completed", f"status={run.get('status') if run else None}")

    status, body = api.request("GET", f"/projects/{pid}/articles?page_size=1")
    total = body.get("total", 0) if status == 200 and isinstance(body, dict) else 0
    check(total > 0, "search returned articles", f"{total} articles")

    for e in events:
        if e.get("event") == "search_error":
            log(f"        search_error from server: {str(e.get('message'))[:300]}")
    if run and run.get("status") != "completed":
        log(f"        run record: {json.dumps({k: v for k, v in run.items() if k != 'source_queries'})[:400]}")
        for sq in run.get("source_queries", []):
            log(f"        source {sq.get('source')}: {sq.get('result_count')} results")
    kinds = sorted({e.get("event", "?") for e in events})
    check(ws_state["connected"], "WebSocket connected", ws_state["error"])
    check("search_progress" in kinds or "search_complete" in kinds, "WebSocket delivered progress events",
          f"{len(events)} events: {', '.join(kinds) or 'none'}")


def delete_project(api: Api, pid: str, label: str) -> None:
    try:
        status, _ = api.request("DELETE", f"/projects/{pid}", timeout=300)
        check(status == 204, f"delete {label}", f"HTTP {status}")
    except Exception as exc:  # noqa: BLE001 - one slow delete must not hide the other results
        check(False, f"delete {label}", f"{type(exc).__name__}: {exc}")


def cleanup(api: Api) -> None:
    log("\n[4] Cleanup (only projects named with the smoke prefix)")
    for pid in created_projects:
        status, body = api.request("GET", f"/projects/{pid}")
        name = body.get("name", "") if isinstance(body, dict) else ""
        if status == 404:
            continue
        if not name.startswith(SMOKE_PREFIX):
            log(f"  SKIP  {pid}: name does not start with the smoke prefix")
            continue
        delete_project(api, pid, pid[:8])
    # Leftovers from an earlier run that crashed before cleaning up.
    status, body = api.request("GET", "/projects")
    if status == 200 and isinstance(body, list):
        for proj in body:
            if proj.get("name", "").startswith(SMOKE_PREFIX) and proj["id"] not in created_projects:
                log(f"  found leftover smoke project {proj['id'][:8]} ({proj['name'][-19:]})")
                delete_project(api, proj["id"], f"leftover {proj['id'][:8]}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("api", help="API base URL, e.g. https://litprism-api.example.azurecontainerapps.io")
    parser.add_argument("--token", default=None, help="Supabase access token (needed once login is enforced)")
    args = parser.parse_args()
    api = Api(args.api, args.token or None)
    ws_base = api.base.replace("https://", "wss://").replace("http://", "ws://")

    log(f"Smoke test against {api.base}\n[1] API is up")
    status, body = api.request("GET", "/openapi.json")
    if not check(status == 200, "GET /openapi.json", f"HTTP {status}"):
        return 1
    status, _ = api.request("GET", "/projects")
    check(status == 200, "GET /projects", f"HTTP {status}" + (" (needs --token?)" if status == 401 else ""))
    if status != 200:
        return 1

    try:
        upload_and_screen(api)
        search_and_progress(api, ws_base)
    finally:
        cleanup(api)

    log("\n" + ("ALL CHECKS PASSED" if not failures else f"{len(failures)} CHECK(S) FAILED: " + "; ".join(failures)))
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
