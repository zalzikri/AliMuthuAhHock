"""Proves the chain cascades, for every combination. Run: .venv/bin/python backend/smoke.py"""
import os
import pathlib
import sys

os.environ["DB_PATH"] = "/tmp/dayone_smoke.db"
pathlib.Path(os.environ["DB_PATH"]).unlink(missing_ok=True)
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from backend.app import engine, servicedesk, store   # noqa: E402

conn = store.connect()
desk = servicedesk.MockServiceDesk(conn, demo_seconds=10_000)   # nothing resolves by itself


def show(oid, label):
    v = engine.view(conn, desk, oid)
    print(f"\n--- {label}  ({v['progress']['done']}/{v['progress']['total']})")
    for s in v["steps"]:
        extra = f"  #{s['ticket_id']}" if s["ticket_id"] else f"  [{s['channel']}]"
        print(f"  {s['state']:<15}{s['title']}{extra}")
    return v


def run(employment, job_family, project):
    label = f"{employment} / {job_family} / {project or 'no project'}"
    print("\n" + "=" * 70 + f"\n{label}")
    oid = engine.create(conn, desk, {
        "name": "Nurul Aina", "starter_email": "zal@gamuda.com.my",
        "employment": employment, "job_family": job_family, "project": project,
        "start_date": "17-11-2026"})
    v = show(oid, "day 0")
    assert sum(1 for s in v["steps"] if s["state"] == "open") == 1, "only the email goes out"

    desk.resolve(next(s for s in v["steps"] if s["id"] == "email")["ticket_id"])
    v = show(oid, "IT resolved the email ticket")
    assert v["work_email"] == "nurul.aina@gamuda.com.my", v["work_email"]
    print(f"  work email read back from the ticket reply: {v['work_email']}")
    assert v["your_turn"]["id"] == "password_reset"

    # GES mails her WORK inbox, so her GES part must wait until she has signed in
    ges = next((s for s in v["steps"] if s["id"] == "ges"), None)
    if ges:
        desk.resolve(ges["ticket_id"])
        v = engine.view(conn, desk, oid)
        ges = next(s for s in v["steps"] if s["id"] == "ges")
        assert ges["state"] == "waiting_user" and ges["held_by"], ges
        assert v["your_turn"]["id"] == "password_reset", "GES must not jump the sign-in"
        engine.confirm(conn, desk, oid, "ges")
        assert next(s for s in engine.view(conn, desk, oid)["steps"]
                    if s["id"] == "ges")["state"] == "waiting_user", "early GES confirm ignored"
        print("  GES granted early, held until she signs in: ok")

    engine.confirm(conn, desk, oid, "password_reset")
    for _ in range(5):
        v = engine.view(conn, desk, oid)
        for s in v["steps"]:
            if s["state"] == "open":
                desk.resolve(s["ticket_id"])
            elif s["state"] == "waiting_user" and s["then_self"]:
                engine.confirm(conn, desk, oid, s["id"])
    v = show(oid, "IT cleared every ticket")

    for s in list(v["steps"]):
        if s["state"] in ("waiting_user", "waiting_person"):
            if s["channel"] == "slack_guided":
                print(f"  slack message written for her: {s['ask'][:70]}...")
            if s["channel"] == "person":
                print(f"  person step -> {v['poc_name']} <{v['poc_email']}>")
                print(f"  message written for her: {s['ask'][:70]}...")
            engine.confirm(conn, desk, oid, s["id"])
    v = show(oid, "finished")
    assert v["progress"]["done"] == v["progress"]["total"], v["progress"]
    return v


a = run("staff", "developer", "odin")
b = run("intern", "developer", "odin")
c = run("staff", "other", None)
d = run("intern", "other", None)

assert [s["id"] for s in a["steps"]].count("gems") == 1
assert "gems" not in [s["id"] for s in b["steps"]]
assert "bitbucket" not in [s["id"] for s in c["steps"]]
print("\ncounts:", {k: v["progress"]["total"] for k, v in
                    (("staff dev", a), ("intern dev", b), ("staff other", c), ("intern other", d))})
print("skipped for intern/other:", [s["title"] for s in d["skipped"]])
print("\nSMOKE OK")
