"""Service desk adapters.

Both speak the Freshservice v2 contract. Switch with SERVICEDESK=mock|freshservice.
Freshservice status codes: 2 Open, 3 Pending, 4 Resolved, 5 Closed.
"""
import os
import time
import sqlite3
from typing import Protocol

RESOLVED = (4, 5)


class ServiceDesk(Protocol):
    def create_ticket(self, subject: str, description: str, email: str) -> dict: ...
    def get_ticket(self, ticket_id: int) -> dict: ...


class MockServiceDesk:
    """A local stand-in for GSD. Same shapes as Freshservice v2.

    Tickets auto-resolve after DEMO_SECONDS so a 3-day wait becomes a few seconds
    on stage. An operator can also resolve one by hand, which is the demo button.
    """

    def __init__(self, conn: sqlite3.Connection, demo_seconds: int = 8):
        self.conn = conn
        self.demo_seconds = demo_seconds

    def create_ticket(self, subject: str, description: str, email: str, manual: bool = False) -> dict:
        now = time.time()
        wait = 10 ** 9 if manual else self.demo_seconds     # a tour ticket waits for the tour
        cur = self.conn.execute(
            "INSERT INTO mock_ticket (subject, description, email, created_at, resolve_at) "
            "VALUES (?,?,?,?,?)",
            (subject, description, email, now, now + wait),
        )
        self.conn.commit()
        return self.get_ticket(int(cur.lastrowid or 0))

    def get_ticket(self, ticket_id: int) -> dict:
        row = self.conn.execute(
            "SELECT id, subject, description, email, created_at, resolve_at, forced "
            "FROM mock_ticket WHERE id=?", (ticket_id,)).fetchone()
        if row is None:
            raise KeyError(ticket_id)
        tid, subject, desc, email, created, resolve_at, forced = row
        resolved = bool(forced) or time.time() >= resolve_at
        note = ""
        if resolved and subject.startswith("New email account for "):
            who = subject[len("New email account for "):].strip()
            parts = [p for p in who.lower().split() if p.isalpha()]
            slug = parts[0] if len(parts) < 2 else f"{parts[0]}.{parts[-1]}"
            note = (f"Account created: {slug}@gamuda.com.my. "
                    "Sign-in details sent to the requester. "
                    "The user sets their own password at first sign-in.")
        return {"id": tid, "subject": subject, "description": desc, "email": email,
                "status": 4 if resolved else 2,
                "status_label": "Resolved" if resolved else "Open",
                "resolution_note": note}

    def resolve(self, ticket_id: int) -> dict:
        self.conn.execute("UPDATE mock_ticket SET forced=1 WHERE id=?", (ticket_id,))
        self.conn.commit()
        return self.get_ticket(ticket_id)

    def list_tickets(self) -> list[dict]:
        ids = [r[0] for r in self.conn.execute(
            "SELECT id FROM mock_ticket ORDER BY id DESC")]
        return [self.get_ticket(i) for i in ids]


class FreshserviceClient:
    """The real thing. Needs an AGENT api key; a requester account cannot get one."""

    def __init__(self, domain: str, api_key: str):
        import httpx
        self.base = f"https://{domain}/api/v2"
        self.http = httpx.Client(auth=(api_key, "X"), timeout=30)

    def create_ticket(self, subject: str, description: str, email: str) -> dict:
        r = self.http.post(f"{self.base}/tickets", json={
            "subject": subject, "description": description,
            "email": email, "priority": 1, "status": 2})
        r.raise_for_status()
        return r.json()["ticket"]

    def get_ticket(self, ticket_id: int) -> dict:
        r = self.http.get(f"{self.base}/tickets/{ticket_id}")
        r.raise_for_status()
        t = r.json()["ticket"]
        t["resolution_note"] = self._last_note(ticket_id) if t["status"] in RESOLVED else ""
        return t

    def _last_note(self, ticket_id: int) -> str:
        """IT writes the new address in a reply. Read it back."""
        r = self.http.get(f"{self.base}/tickets/{ticket_id}/conversations")
        if r.status_code != 200:
            return ""
        items = r.json().get("conversations", [])
        return items[-1].get("body_text", "") if items else ""


def build(conn) -> ServiceDesk:
    kind = os.getenv("SERVICEDESK", "mock").lower()
    if kind == "freshservice":
        return FreshserviceClient(os.environ["FRESHSERVICE_DOMAIN"],
                                  os.environ["FRESHSERVICE_API_KEY"])
    return MockServiceDesk(conn, int(os.getenv("DEMO_SECONDS", "8")))
