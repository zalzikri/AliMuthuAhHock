# Day One — PRD

**Team:** Ali Muthu Ah Hock · **Event:** Gamuda Tech hackathon · **Track:** Work (with a Serve edge)
**Deadline:** 2026-11-13, 10:48 · **Status:** agreed scope, building

---

## 1. One paragraph

A new Gamuda Tech developer waits 12 to 20 working days before they can push code. Not because
IT is slow, but because the access chain is serial, tribal and human-driven: somebody must
remember to raise the next ticket, in the right channel, in the right order. **Day One** knows
the sequence, raises every request itself, tracks it against the real service desk, and tells the
new hire the single thing that is their turn today. While they wait, it serves them the GTech
documentation they are allowed to read — which they otherwise cannot open, because the docs site
is behind a Google login they receive on day five.

---

## 2. The problem, with evidence

| Claim | Evidence | Mark |
|---|---|---|
| The chain is serial. Each step blocks the next. | Zal, GT developer. Email → GEMS/GES/GSD → Bitbucket/Slack/Atlassian → repo. | fact |
| Each step takes 3–5 days. | Zal. | fact |
| So a developer waits 12–20 working days. | 4 serial hand-offs × 3–5 days. | derived |
| Interns depend on the buddy for everything. | They never get GSD, so they cannot raise their own tickets. | fact |
| There are two request channels and new hires confuse them. | `gtech-docs/apps/docs/platform/requests/index.md`: `/gcp-request` in Slack for GCP, GSD for everything else, and "when in doubt, start with `/gcp-request`". | fact |
| The instructions are unreachable on day one. | `docs-internal.gamuda.tech` sits behind Google IAP; the Google account is step 1 of the chain. | fact, verified by probe |
| Nobody can see where a new hire is stuck. | No system holds the chain. | belief |

**The line for the deck:** *the onboarding documentation sits behind a login you receive on day five.*

---

## 3. Users

**One screen. One URL. No roles.** Anyone holding the link can start a hire — buddy, supervisor,
HR, or the new hire. The page shows the start form when the hire does not exist yet, and the
status afterwards. There is no separate starter screen and no IT screen: IT already works inside
GSD, and nothing we build should ask them to leave it.

In the demo, requests resolve on a timer. A hidden control at `?demo=1` forces the next one, for
manual stage timing.

---

## 4. Scope

**In**
- The real GT access chain as a dependency graph, with two axes of variation.
- Automatic request raising against a Freshservice-contract service desk.
- Automatic status tracking. No checkboxes.
- A single "your turn" card with four states.
- A reading list that follows the access the hire actually holds.
- A product directory built from the `gtech-docs` repo.
- Point of contact on every step that needs a human.

**Out**
- Creating Google Workspace, GEMS or GES accounts. Those need super-admin. We automate the
  *request*, never the *grant*. Say this on stage.
- A buddy dashboard of all hires.
- Any coaching beyond "you have everything".
- Real Slack, Jira or Bitbucket writes.

---

## 5. The access model — two axes, not one list

Access is decided by **employment type × job family**. The project is optional and only adds
project-specific items.

| Step | Intern | Staff | Non-developer | Developer | Channel |
|---|---|---|---|---|---|
| Google Workspace email | ✓ | ✓ | ✓ | ✓ | GSD, automatic |
| Set your password | ✓ | ✓ | ✓ | ✓ | the new hire |
| GEMS (SuccessFactors) | — | ✓ | ✓ | ✓ | GSD, automatic |
| GES | — | ✓ | ✓ | ✓ | GSD, automatic |
| GSD portal access | — | ✓ | ✓ | ✓ | GSD, automatic |
| Slack | ✓ | ✓ | ✓ | ✓ | GSD, automatic |
| Atlassian | ✓ | ✓ | ✓ | ✓ | GSD, automatic |
| Bitbucket account | ✓ | ✓ | — | ✓ | GSD, automatic |
| GCP project access | ✓ | ✓ | — | ✓ | **Slack, guided** |
| Add to the project repo | ✓ | ✓ | — | ✓ | **named person** |
| Claude Code seat | optional | optional | optional | optional | GSD, automatic |

Interns skip GEMS, GES and GSD, so for them every remaining request hangs off the email step and
the starter raises it all.

### Four channel kinds

| Channel | Behaviour |
|---|---|
| `gsd_auto` | Day One raises the ticket through the service desk API and polls its status. Where a named person must action it, the point of contact is shown on the step. |
| `slack_guided` | Day One cannot post to Slack. It shows the exact command and a pre-filled message to copy. The hire confirms when sent. |
| `self` | The hire does it. One button to confirm. |

Three kinds, not four. The repo add is `gsd_auto` like everything else: Bitbucket has no public
API for *requesting* access, only for granting it, which needs an admin token. So Day One asks on
her behalf through the channel it already automates, and names the person who must act.

`slack_guided` is the honest answer to GCP access, and it carries the insight nobody tells a new
hire: **GCP goes through Slack, everything else goes through GSD.**

---

## 6. Features

| # | Feature | Priority |
|---|---|---|
| F1 | Start form: name, personal email, employment type, job family, project (optional) | P0 |
| F2 | Dependency engine: raise, wait, release | P0 — **done** |
| F3 | Service desk adapter: local stand-in plus the real Freshservice client | P0 — **done** |
| F4 | New hire page, signed link, no password | P0 |
| F5 | "Your turn" card, four states | P0 |
| F6 | Timer-driven resolution, plus a hidden `?demo=1` control for stage timing | P0 |
| F7 | Product directory from `gtech-docs`, Design 1 cards | P1 |
| F8 | Reading list filtered by the access she holds, served from the repo | P1 |
| F9 | POC name and email on every `poc` and `slack_guided` step | P1 |
| F10 | Intern and non-developer toggles visibly change the plan | P1 |

---

## 7. Screens

**A. Start a hire.** Six fields. One button. Then a confirmation naming what was raised.

**B. Their page.** Top: exactly one "your turn" card.
- *State A — act:* "Set your password", with a button.
- *State B — nothing to do:* "Bitbucket is with IT. Ticket #41882, 2 days left." plus the next page to read.
- *State C — a person is the blocker:* "Jeremy must add you to gt-odin", with his email.
- *State D — finished:* "You have everything. 8 of 8 in 4 days."

Below: the quiet step list. Beside: the reading list and product cards.

There is no third screen. See `sketch/flow-ux.html` for the wireframe.

---

## 8. Data

- `backend/app/flow.py` — the step graph, the two axes, the four channels.
- `data/projects.json` — per project: repo, docs section, Slack channel, POC name and email.
  Demo values: Odin–Jeremy, SpatialQ–Carter, Trudax–Ian, GT-Console–Iqhwan. **Dummy until Zal
  supplies the real contacts and URLs.**
- `~/work/gtech-docs` — 21 product sections under `apps/docs/`, each with its own sidebar and
  declared reading order. The directory and reading list are generated from this, not typed.
- Doc URLs resolve as `https://docs-internal.gamuda.tech/apps/<product>/<page>`, with `platform`
  and `incidents` at the root. Day One renders the markdown locally, because the hire cannot
  reach that site yet.

---

## 9. Honesty boundary

Say this one on stage:
1. The service desk in the demo is a local stand-in. The client speaks the real Freshservice
   `/api/v2` contract; one environment variable points it at `gamuda.freshservice.com`.
   We could not use the real one because a requester account cannot hold an API key.

Keep these as prepared answers, not slides:
2. Day One raises requests; IT still fulfils them. Expect this question and answer it plainly.
3. The Bitbucket repo add needs a repo admin token to be granted automatically, so Day One asks
   rather than grants.
4. Contact names and emails are dummy. Product URLs are real.

---

## 10. Demo, three beats

1. **Start.** Fill the form for a staff developer on Odin. Press start. One ticket goes out, not
   eleven — because the rest are blocked. Switch the toggle to Intern and show the plan change
   from 11 steps to 8, with GEMS, GES and GSD gone.
2. **The cascade.** Resolve the email ticket in the service desk view. Her page instantly says
   "Set your password". Confirm it. Three more requests fire by themselves. Her reading list
   grows at the same moment.
3. **The wait, made useful.** Land on State C: Jeremy must add her to `gt-odin`, here is his
   email. Beside it, the directory of 21 GTech products, built from the docs repo with nobody
   typing them in. Close on: *"she read this on day one, and the docs site needs an account she
   gets on day five."*

---

## 11. Hours

| Time | Work | Gate |
|---|---|---|
| 20:00–21:30 | F1, F5, F6 — start form, your-turn card, service desk view | The cascade is visible in a browser |
| 21:30–22:30 | F4 signed link, F10 toggles | Intern plan differs on screen |
| 22:30–23:30 | F7, F8 — directory and reading list from `gtech-docs` | 21 products render |
| 23:30–00:15 | Demo script, seed data, **record the backup video** | **Feature freeze 00:15** |
| 00:15–07:15 | Sleep, 7 hours | Not optional |
| 07:15–09:00 | Bugs only. Two clean rehearsals | Two crash-free runs |
| 09:00–10:15 | Deck. Final run | No code after 10:15 |

---

## 12. Risks

| Risk | Mitigation |
|---|---|
| "This is Agentlinc." | Agentlinc answers when asked. Day One acts without being asked, and acts on systems. |
| "GSD already has onboarding." | GSD raises a ticket. It does not know the sequence, the intern branch, the two channels, or the repo admin. |
| Scope creep into a 14-day plan | Out of scope. We stop at "you have everything". |
| Docs rendering eats the evening | F8 degrades to a link list. Decide at 23:00. |

---

## 13. Open

1. Real POC emails and product URLs.
2. Confirm the Slack channel for GCP requests: the docs say the `/gcp-request` command posts to
   `#gcp-requests`; Zal said `#devops-request`.
3. Real product URLs for the cards.
