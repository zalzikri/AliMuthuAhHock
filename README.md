# Day One

**KopiCode 2026 - team Ali Muthu Ah Hock**

A new Gamuda Tech joiner waits 12 to 20 working days before they can push code. Not
because IT is slow: the access chain is serial, tribal and human-driven, and somebody
has to remember to raise the next request, in the right channel, in the right order.

**Day One knows the sequence, raises every request itself, tracks it against the
service desk, and shows the new joiner the one thing that is their turn today.**

## What it does

- Models the real access chain as a dependency graph. Two axes decide who gets what:
  employment (staff or intern) and job family (developer or not).
- Raises each request as soon as its blockers clear, through four channels: an
  automatic service-desk ticket, a guided Slack request, something the joiner does,
  or a named person.
- Reads status back from the service desk. No checkboxes.
- Shows one card at a time: your turn, or who is holding it and for how long.
- Fills the wait with the GTech product directory and the docs they can reach.

## Data and honesty

The hackathon rules allow dummy or public data only, so:

- The service desk is a local stand-in that speaks the **real Freshservice `/api/v2`
  contract**. `SERVICEDESK=freshservice` with a domain and an agent key points the
  same code at the real one.
- Product descriptions and links are public. Internal documentation is linked,
  never copied.
- Contact names and addresses are invented.

## Run it

```bash
pip install -r requirements.txt
uvicorn backend.app.main:app --port 8077      # http://localhost:8077
python backend/smoke.py                       # proves the chain cascades
```

`DEMO_SECONDS` controls how fast the stand-in resolves a request, so a three-day wait
plays out in seconds on stage.
