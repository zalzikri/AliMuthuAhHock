"""The orchestrator: ask for each access as soon as its blockers clear."""
import json
import re
import secrets
import time
from pathlib import Path

from . import flow

BLOCKED, OPEN, WAIT_USER, WAIT_PERSON, DONE = (
    "blocked", "open", "waiting_user", "waiting_person", "done")

ROOT = Path(__file__).resolve().parents[2]
PROJECTS = json.loads((ROOT / "data" / "projects.json").read_text())
EMAIL_RE = re.compile(r"[\w.+-]+@gamuda\.com\.my")

def guess_email(name: str) -> str:
    """Simulation only. IT decides the real address when they create the account."""
    parts = [p for p in (name or "").lower().split() if p.isalpha()]
    if not parts:
        return ""
    local = parts[0] if len(parts) == 1 else f"{parts[0]}.{parts[-1]}"
    return f"{local}@gamuda.com.my"


FIELDS = ("id", "token", "name", "employment", "job_family", "project", "start_date",
          "starter_email", "personal_email", "work_email", "bitbucket_user", "want_claude", "manual")


def _row(conn, oid) -> dict | None:
    r = conn.execute(f"SELECT {', '.join(FIELDS)} FROM onboarding WHERE id=?", (oid,)).fetchone()
    return dict(zip(FIELDS, r)) if r else None


def _ctx(o: dict) -> dict:
    p = PROJECTS.get(o["project"] or "", {})
    first = (o["name"] or "").split()[0] if o["name"] else "there"
    return {
        "name": o["name"], "employment": o["employment"], "job_family": o["job_family"],
        "project": o["project"] or "no project yet", "start_date": o["start_date"] or "soon",
        "project_clause": f", joining {o['project']}" if o["project"] else "",
        "poc_name": p.get("poc_name", "the project admin"),
        "poc_first": p.get("poc_name", "there"),
        "poc_email": p.get("poc_email", ""),
        "repo": p.get("repo", "the repo"),
        "gcp_project": p.get("gcp_project", "the project"),
        "work_email": o["work_email"] or guess_email(o["name"]) or "your new Gamuda address",
        "starter": o["starter_email"] or "your buddy",
        "job_title": "backend developer" if o["job_family"] == "developer" else "joiner",
        "first": first,
    }


def create(conn, desk, data: dict) -> int:
    now = time.time()
    token = secrets.token_urlsafe(9)
    cur = conn.execute(
        "INSERT INTO onboarding (token, name, employment, job_family, project, start_date,"
        " starter_email, personal_email, want_claude, manual, created_at)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (token, data["name"], data.get("employment", "staff"),
         data.get("job_family", "developer"), data.get("project") or None,
         data.get("start_date", ""), data.get("starter_email", ""),
         data.get("personal_email", ""), int(data.get("want_claude", True)),
         int(bool(data.get("manual", False))), now))
    oid = cur.lastrowid
    for s in flow.plan(data.get("employment", "staff"), data.get("job_family", "developer"),
                       data.get("project") or None, data.get("want_claude", True)):
        conn.execute("INSERT INTO step (onboarding_id, step_id, state, updated_at)"
                     " VALUES (?,?,?,?)", (oid, s.id, BLOCKED, now))
    conn.commit()
    advance(conn, desk, oid)
    return oid


def _states(conn, oid):
    return {r[0]: r[1] for r in conn.execute(
        "SELECT step_id, state FROM step WHERE onboarding_id=?", (oid,))}


def _set(conn, oid, step_id, state, ticket_id=None):
    if ticket_id is None:
        conn.execute("UPDATE step SET state=?, updated_at=? WHERE onboarding_id=? AND step_id=?",
                     (state, time.time(), oid, step_id))
    else:
        conn.execute("UPDATE step SET state=?, ticket_id=?, updated_at=?"
                     " WHERE onboarding_id=? AND step_id=?",
                     (state, ticket_id, time.time(), oid, step_id))
    conn.commit()


def advance(conn, desk, oid: int) -> None:
    o = _row(conn, oid)
    if not o:
        return
    assert o is not None
    ctx = _ctx(o)
    requester = o["starter_email"] or o["personal_email"] or "unknown@gamuda.com.my"

    for _ in range(len(flow.STEPS) + 1):
        changed = False

        for step_id, ticket_id in conn.execute(
                "SELECT step_id, ticket_id FROM step WHERE onboarding_id=? AND state=?",
                (oid, OPEN)).fetchall():
            if ticket_id is None:
                continue
            t = desk.get_ticket(ticket_id)
            if t["status"] in (4, 5):
                granted = flow.STEP_BY_ID[step_id]
                _set(conn, oid, step_id, WAIT_USER if granted.then_self else DONE)
                changed = True
                if step_id == "email" and not o["work_email"]:
                    found = EMAIL_RE.search(t.get("resolution_note") or "")
                    if found:
                        conn.execute("UPDATE onboarding SET work_email=? WHERE id=?",
                                     (found.group(0), oid))
                        conn.commit()
                        o = _row(conn, oid)
                        assert o is not None

        states = _states(conn, oid)
        for step_id, state in states.items():
            if state != BLOCKED:
                continue
            s = flow.STEP_BY_ID[step_id]
            deps = flow.deps_for(s, o["employment"])
            if not all(states.get(d) == DONE for d in deps if d in states):
                continue
            if s.channel == flow.GSD_AUTO:
                if o["manual"] and hasattr(desk, "resolve"):
                    t = desk.create_ticket(s.subject.format(**ctx), s.body.format(**ctx), requester,
                                           manual=True)
                else:
                    t = desk.create_ticket(s.subject.format(**ctx), s.body.format(**ctx), requester)
                _set(conn, oid, step_id, OPEN, int(t["id"]))
            elif s.channel == flow.PERSON:
                _set(conn, oid, step_id, WAIT_PERSON)
            else:                                  # self, slack_guided
                _set(conn, oid, step_id, WAIT_USER)
            changed = True

        if not changed:
            return


def confirm(conn, desk, oid: int, step_id: str, work_email: str = "") -> None:
    if work_email:
        set_work_email(conn, oid, work_email.strip())
    states = _states(conn, oid)
    held = any(states.get(d) not in (None, DONE) for d in flow.STEP_BY_ID[step_id].self_after)
    if states.get(step_id) in (WAIT_USER, WAIT_PERSON) and not held:
        _set(conn, oid, step_id, DONE)
    advance(conn, desk, oid)


def resolve_next(conn, desk, oid: int) -> None:
    """Demo only: IT resolves the oldest open request of THIS hire."""
    row = conn.execute("SELECT MIN(ticket_id) FROM step WHERE onboarding_id=? AND state=?"
                       " AND ticket_id IS NOT NULL", (oid, OPEN)).fetchone()
    if row and row[0] is not None:
        desk.resolve(row[0])
    advance(conn, desk, oid)


def set_work_email(conn, oid: int, email: str) -> None:
    conn.execute("UPDATE onboarding SET work_email=? WHERE id=?", (email, oid))
    conn.commit()


def _link_hours_left(conn, oid: int) -> float | None:
    """Google's welcome link dies 48h after IT sends it. Count it down."""
    row = conn.execute("SELECT state, updated_at FROM step"
                       " WHERE onboarding_id=? AND step_id='email'", (oid,)).fetchone()
    if not row or row[0] != DONE:
        return None
    left = (row[1] + 48 * 3600 - time.time()) / 3600
    return round(left, 1)


def view(conn, desk, oid: int) -> dict:
    advance(conn, desk, oid)
    o = _row(conn, oid)
    if not o:
        raise KeyError(oid)
    ctx = _ctx(o)
    out: dict = dict(o)
    out["poc_name"] = ctx["poc_name"]
    out["poc_email"] = ctx["poc_email"]
    steps = []
    for step_id, state, ticket_id in conn.execute(
            "SELECT step_id, state, ticket_id FROM step WHERE onboarding_id=? ORDER BY id",
            (oid,)):
        s = flow.STEP_BY_ID[step_id]
        age_days = None
        steps.append({
            "id": s.id, "title": s.title, "system": s.system, "channel": s.channel,
            "eta_days": s.eta_days, "optional": s.optional, "state": state,
            "ticket_id": ticket_id, "age_days": age_days,
            "hint": s.hint.format(**ctx) if s.hint else "",
            "ask": s.ask.format(**ctx) if s.ask else "",
            "fields": [{"label": k, "value": v.format(**ctx)} for k, v in s.fields],
            "howto": [h.format(**ctx) for h in s.howto],
            "then_self": s.then_self,
            "blocked_by": [flow.STEP_BY_ID[d].title
                           for d in flow.deps_for(s, o["employment"])
                           if d in flow.STEP_BY_ID],
        })
    by_id = {s["id"]: s for s in steps}
    for s in steps:   # granted by IT, but her part needs another step first (GES needs her inbox)
        s["held_by"] = [by_id[d]["title"] for d in flow.STEP_BY_ID[s["id"]].self_after
                        if d in by_id and by_id[d]["state"] != DONE] if s["state"] == WAIT_USER else []
    out["steps"] = steps
    done = sum(1 for s in steps if s["state"] == DONE)
    out["progress"] = {"done": done, "total": len(steps)}
    out["skipped"] = [{"title": t, "why": w} for t, w in
                      flow.skipped(o["employment"], o["job_family"], o["project"])]
    out["guess_email"] = guess_email(o["name"])
    out["link_expires_in_hours"] = _link_hours_left(conn, oid)
    for s in steps:
        s["ask_email"] = (s["id"] == "password_reset" and not o["work_email"])
    mine = [s for s in steps if s["state"] in (WAIT_USER, WAIT_PERSON) and not s["held_by"]]
    out["your_turn"] = mine[0] if mine else None
    out["your_turn_count"] = len(mine)
    out["waiting_on"] = next((s for s in steps if s["state"] == OPEN), None)
    return out


def preview(employment: str, job_family: str, project: str | None, want_claude: bool) -> dict:
    """What the form shows beside the fields, before anything is created."""
    return {
        "steps": [{"id": s.id, "title": s.title, "channel": s.channel, "optional": s.optional}
                  for s in flow.plan(employment, job_family, project, want_claude)],
        "skipped": [{"title": t, "why": w} for t, w in
                    flow.skipped(employment, job_family, project)],
    }
