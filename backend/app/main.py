import json
import os
import re
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import directory, engine, servicedesk, store

ROOT = Path(__file__).resolve().parents[2]
conn = store.connect()
desk = servicedesk.build(conn)

app = FastAPI(title="Day One")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"],
                   allow_headers=["*"])


class NewHire(BaseModel):
    name: str
    starter_email: str
    employment: str = "staff"            # staff | intern
    job_family: str = "developer"        # developer | other
    project: str | None = None
    start_date: str = ""
    want_claude: bool = True
    manual: bool = False                  # demo tour: tickets wait for the tour


def _oid_for_token(token: str) -> int:
    row = conn.execute("SELECT id FROM onboarding WHERE token=?", (token,)).fetchone()
    if row is None:
        raise HTTPException(404, "no such page")
    return row[0]


@app.get("/api/preview")
def preview(employment: str = "staff", job_family: str = "developer",
            project: str | None = None, want_claude: bool = True):
    return engine.preview(employment, job_family, project, want_claude)


GAMUDA = re.compile(r"^[^@\s]+@(gamuda\.com\.my|gamuda\.tech)$", re.I)


@app.post("/api/onboardings")
def create(h: NewHire):
    # Only Gamuda staff start onboarding: a new hire has no Gamuda email yet.
    if not GAMUDA.match(h.starter_email.strip()):
        raise HTTPException(400, "Use your Gamuda work email. Only Gamuda staff can start onboarding.")
    oid = engine.create(conn, desk, h.model_dump())
    return engine.view(conn, desk, oid)


@app.get("/api/n/{token}")
def show(token: str):
    return engine.view(conn, desk, _oid_for_token(token))


@app.post("/api/n/{token}/steps/{step_id}/confirm")
def confirm(token: str, step_id: str, payload: dict | None = None):
    oid = _oid_for_token(token)
    engine.confirm(conn, desk, oid, step_id, (payload or {}).get("work_email", ""))
    return engine.view(conn, desk, oid)


@app.post("/api/n/{token}/demo/next")
def demo_next_for(token: str):
    """Stage control for one hire: IT resolves its oldest open request."""
    if not isinstance(desk, servicedesk.MockServiceDesk):
        raise HTTPException(400, "resolve it in Freshservice instead")
    oid = _oid_for_token(token)
    engine.resolve_next(conn, desk, oid)
    return engine.view(conn, desk, oid)


@app.post("/api/n/{token}/work-email")
def work_email(token: str, payload: dict):
    oid = _oid_for_token(token)
    engine.set_work_email(conn, oid, payload.get("email", ""))
    return engine.view(conn, desk, oid)


@app.get("/api/projects")
def projects():
    return json.loads((ROOT / "data" / "projects.json").read_text())


@app.post("/api/demo/next")
def demo_next():
    """Stage control: resolve the oldest open request."""
    if not isinstance(desk, servicedesk.MockServiceDesk):
        raise HTTPException(400, "resolve it in Freshservice instead")
    for t in sorted(desk.list_tickets(), key=lambda x: x["id"]):
        if t["status"] not in (4, 5):
            return desk.resolve(t["id"])
    return {"ok": True, "note": "nothing open"}


@app.get("/api/directory")
def api_directory():
    return directory.build()


@app.get("/api/quiz")
def quiz():
    """Slot for the challenge-round quiz. Replace with the real question bank."""
    path = ROOT / "data" / "quiz.json"
    return json.loads(path.read_text()) if path.exists() else {"questions": []}


@app.get("/api/health")
def health():
    return {"ok": True, "servicedesk": os.getenv("SERVICEDESK", "mock")}


INDEX = ROOT / "frontend" / "index.html"
app.mount("/brand", StaticFiles(directory=ROOT / "frontend" / "brand"), name="brand")


@app.get("/")
@app.get("/n/{token}")
def page(token: str = ""):
    return FileResponse(INDEX)
