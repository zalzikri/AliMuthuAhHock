"""Puncak: the "while you wait" mini game.

Seven questions a day about Gamuda. Each asks the player to name one thing; points move
them up a mountain, and 80% of the maximum reaches the summit. The page lives in
frontend/puncak, the questions in data/puncak.json.

Two kinds of question:
  binary  any correct answer scores 100
  rarity  each answer is common (40), rare (70) or very rare (100)
"""
import json
import os
import re
import threading
import time
import unicodedata
from datetime import date
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import JSONResponse

ROOT = Path(__file__).resolve().parents[2]
QUESTIONS_PATH = ROOT / "data" / "puncak.json"
# Scores sit next to the onboarding database, so one setting moves both.
STATE_PATH = Path(os.getenv("PUNCAK_STATE") or
                  Path(os.getenv("DB_PATH", "onboarding.db")).with_name("puncak-state.json"))

TIME_LIMIT_MS = 30_000      # per question
GRACE_MS = 1_500            # network slack on top of the limit
MAX_GUESSES = 8             # stops brute-forcing inside the time limit
FIRST_CLIMB = date(2026, 11, 12)
TIER_POINTS = {"common": 40, "rare": 70, "very rare": 100}
SUMMIT_SHARE = 0.8          # this share of the maximum score is the summit

router = APIRouter(prefix="/api/puncak")
_lock = threading.Lock()


# ---- answer matching --------------------------------------------------------

def normalize(text) -> str:
    s = unicodedata.normalize("NFKD", str(text or ""))
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    s = re.sub(r"^[#@\s]+", "", s)
    s = re.sub(r"[-_./]+", " ", s)
    s = re.sub(r"[^a-z0-9 ]", "", s)
    return re.sub(r"\s+", " ", s).strip()


def squash(text) -> str:
    return normalize(text).replace(" ", "")


def edit_distance(a: str, b: str) -> int:
    prev = list(range(len(b) + 1))
    for i in range(1, len(a) + 1):
        row = [i]
        for j in range(1, len(b) + 1):
            row.append(min(prev[j] + 1, row[j - 1] + 1, prev[j - 1] + (a[i - 1] != b[j - 1])))
        prev = row
    return prev[len(b)]


def allowed_typos(length: int) -> int:
    return 2 if length >= 9 else 1 if length >= 5 else 0


def keys_of(answer: dict) -> list[str]:
    return [squash(k) for k in [answer["text"], *answer.get("aliases", [])]]


def near_miss(typed: str, answers: list[dict]):
    """The one answer a typo points at, or None when no answer or several are that close."""
    best, best_distance, tied = None, None, False
    for answer in answers:
        for key in keys_of(answer):
            distance = edit_distance(typed, key)
            if distance > allowed_typos(len(key)):
                continue
            if best_distance is None or distance < best_distance:
                best, best_distance, tied = answer, distance, False
            elif distance == best_distance and answer is not best:
                tied = True
    return None if tied else best


def resolve_answer(typed_raw, answers: list[dict]) -> dict:
    """An exact answer (or alias) is a hit. A typo or a partial answer that points at exactly
    one answer comes back as a suggestion for the player to confirm."""
    typed = squash(typed_raw)
    if not typed:
        return {}
    for answer in answers:
        if typed in keys_of(answer):
            return {"hit": answer}
    near = near_miss(typed, answers)
    if near:
        return {"suggestion": near}
    if len(typed) >= 3:
        partial = [a for a in answers if any(typed in key for key in keys_of(a))]
        if len(partial) == 1:
            return {"suggestion": partial[0]}
    return {}


def with_first_name_aliases(answers: list[dict]) -> list[dict]:
    """First names count as answers when only one answer in the set has that first name."""
    first = lambda a: normalize(a["text"]).split(" ")[0]
    seen: dict[str, int] = {}
    for a in answers:
        seen[first(a)] = seen.get(first(a), 0) + 1
    out = []
    for a in answers:
        f = first(a)
        if seen[f] == 1 and len(f) >= 3 and f != normalize(a["text"]):
            a = {**a, "aliases": [*a.get("aliases", []), f]}
        out.append(a)
    return out


# ---- scoring ----------------------------------------------------------------

def tiers_for(q: dict) -> dict:
    """The level of each answer in a rarity question: its own tier, or thirds by how obvious it is."""
    ordered = sorted(q["answers"], key=lambda a: -(a.get("weight") or 0))
    third = len(ordered) / 3
    tiers = {}
    for i, a in enumerate(ordered):
        tier = a.get("tier")
        tiers[a["text"]] = tier if tier in TIER_POINTS else \
            "common" if i < third else "rare" if i < 2 * third else "very rare"
    return tiers


def ranked(q: dict) -> list[dict]:
    """Every answer with its points, best first."""
    tiers = tiers_for(q) if q.get("type") == "rarity" else {}
    rows = []
    for a in q["answers"]:
        row = {"text": a["text"], "points": TIER_POINTS[tiers[a["text"]]] if tiers else 100}
        if a["text"] in tiers:
            row["tier"] = tiers[a["text"]]
        if a.get("note"):
            row["note"] = a["note"]
        rows.append(row)
    return sorted(rows, key=lambda r: -r["points"])


# ---- questions and scores -----------------------------------------------------

def load_daily() -> dict:
    bank = json.loads(QUESTIONS_PATH.read_text())
    today = date.today()
    return {
        "date": today.isoformat(),
        "number": (today - FIRST_CLIMB).days + 1,
        "company": bank.get("company", "Gamuda"),
        "questions": bank["questions"],
    }


def _load_state() -> dict:
    try:
        return json.loads(STATE_PATH.read_text())
    except (OSError, ValueError):
        return {"counts": {}, "plays": {}}


state = _load_state()


def save_state() -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state))


def now_ms() -> int:
    return int(time.time() * 1000)


def clean_name(raw) -> str | None:
    name = re.sub(r"\s+", " ", str(raw or "")).strip()[:24]
    return name or None


def answers_for(day: str, name: str | None) -> dict:
    if not name:
        return {}
    return state["plays"].get(day, {}).get(name.lower(), {}).get("answers", {})


def record_for(day: str, name: str, qid: str) -> dict:
    play = state["plays"].setdefault(day, {}).setdefault(name.lower(), {"name": name, "answers": {}})
    return play["answers"].setdefault(
        qid, {"attempts": 0, "done": False, "points": 0, "answer": None, "startedAt": None})


def remaining_ms(record: dict) -> int:
    return max(0, (record["startedAt"] or now_ms()) + TIME_LIMIT_MS - now_ms())


def public_question(q: dict) -> dict:
    return {"id": q["id"], "type": q.get("type", "binary"), "category": q["category"],
            "prompt": q["prompt"], "blurb": q.get("blurb", ""), "answerCount": len(q["answers"])}


def error(status: int, message: str) -> JSONResponse:
    return JSONResponse({"error": message}, status_code=status)


# ---- routes -------------------------------------------------------------------

@router.get("/daily")
def daily(player: str = ""):
    d = load_daily()
    mine = answers_for(d["date"], clean_name(player))
    return {
        "date": d["date"], "number": d["number"], "company": d["company"],
        "timeLimitMs": TIME_LIMIT_MS,
        "summitScore": round(len(d["questions"]) * 100 * SUMMIT_SHARE),
        "questions": [public_question(q) for q in d["questions"]],
        "progress": {qid: {"done": r["done"], "points": r["points"], "answer": r["answer"]}
                     for qid, r in mine.items()},
    }


@router.post("/start")
def start(body: dict):
    """Starts the clock for a question. Calling it again does not restart the clock."""
    d = load_daily()
    name = clean_name(body.get("player"))
    if not name:
        return error(400, "Player name is required")
    qid = body.get("questionId")
    if not any(q["id"] == qid for q in d["questions"]):
        return error(404, "Unknown question")
    with _lock:
        record = record_for(d["date"], name, qid)
        if not record["startedAt"]:
            record["startedAt"] = now_ms()
            save_state()
        return {"done": record["done"], "remainingMs": remaining_ms(record)}


@router.post("/answer")
def answer(body: dict):
    d = load_daily()
    name = clean_name(body.get("player"))
    if not name:
        return error(400, "Player name is required")
    q = next((q for q in d["questions"] if q["id"] == body.get("questionId")), None)
    if q is None:
        return error(404, "Unknown question")
    gave_up = body.get("giveUp") is True
    order = ranked(q)

    with _lock:
        record = record_for(d["date"], name, q["id"])
        record["startedAt"] = record["startedAt"] or now_ms()
        if not record["done"]:
            out_of_time = now_ms() > record["startedAt"] + TIME_LIMIT_MS + GRACE_MS
            # People can be named by first name alone. A near miss is offered back, not counted as a guess.
            accepted = with_first_name_aliases(q["answers"]) if q["category"] == "People" else q["answers"]
            found = {} if out_of_time or gave_up else resolve_answer(body.get("answer"), accepted)
            hit, suggestion = found.get("hit"), found.get("suggestion")
            if not hit and suggestion:
                save_state()
                return {"done": False, "suggestion": suggestion["text"],
                        "attempts": record["attempts"], "remainingMs": remaining_ms(record)}
            if hit:
                record["points"] = next(a["points"] for a in order if a["text"] == hit["text"])
                record["answer"] = hit["text"]
                record["done"] = True
                counts = state["counts"].setdefault(d["date"], {}).setdefault(q["id"], {})
                counts[hit["text"]] = counts.get(hit["text"], 0) + 1
            else:
                if not out_of_time and not gave_up:
                    record["attempts"] += 1
                if out_of_time or gave_up or record["attempts"] >= MAX_GUESSES:
                    record["done"] = True
            save_state()

        out = {"done": record["done"], "points": record["points"], "answer": record["answer"],
               "attempts": record["attempts"], "remainingMs": remaining_ms(record)}
        if record["done"]:
            theirs = next((a for a in order if a["text"] == record["answer"]), {})
            out.update({
                "type": q.get("type", "binary"),
                "answerCount": len(q["answers"]),
                # The best answer the player did not give, to show what else would have counted.
                "rarest": next((a for a in order if a["text"] != record["answer"]), order[0]),
                "commonest": order[-1],
            })
            if theirs.get("tier"):
                out["tier"] = theirs["tier"]
            if theirs.get("note"):
                out["note"] = theirs["note"]
        return out


@router.get("/results")
def results(player: str = ""):
    d = load_daily()
    mine = answers_for(d["date"], clean_name(player))
    if not all(mine.get(q["id"], {}).get("done") for q in d["questions"]):
        return error(403, "Finish today's climb to see the answers")
    board = []
    for play in state["plays"].get(d["date"], {}).values():
        done = [r for r in play["answers"].values() if r["done"]]
        if len(done) == len(d["questions"]):
            board.append({"name": play["name"], "score": sum(r["points"] for r in done), "finished": True})
    board.sort(key=lambda row: -row["score"])
    return {
        "date": d["date"], "number": d["number"],
        "questions": [{**public_question(q),
                       "yours": {"points": mine[q["id"]]["points"], "answer": mine[q["id"]]["answer"]},
                       "answers": ranked(q)} for q in d["questions"]],
        "leaderboard": board[:20],
    }


@router.get("/climbers")
def climbers(player: str = ""):
    """Everyone who has answered at least one question today, with their score so far."""
    d = load_daily()
    me = (clean_name(player) or "").lower()
    rows = []
    for play in state["plays"].get(d["date"], {}).values():
        if play["name"].lower() == me:
            continue
        done = [r for r in play["answers"].values() if r["done"]]
        if done:
            rows.append({"name": play["name"], "score": sum(r["points"] for r in done), "answered": len(done)})
    return {"climbers": rows[:200]}
