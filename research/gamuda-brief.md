# Gamuda + Gamuda Tech — hackathon research brief

Date: 2026-11-12. Sources: Gamuda 4QFY26 investor briefing (29 Sep 2026), gamuda.com, gamuda.tech, public news.

---

## 1. What Gamuda is, in numbers (FY26, year ended 31 Jul 2026)

| Item | Value | Note |
|---|---|---|
| Group revenue | RM18.6b | +14% |
| Group net profit | RM1,052m | +5%, 5th record year |
| Construction net profit | RM742m | +19% |
| Construction net margin | 5.0% | flat |
| — Malaysia construction margin | 7.8% | net profit +49% |
| — Overseas construction margin | 3.1% | down from 3.7%, net profit −11% |
| Property net profit | RM311m | −18%; Malaysia −47% |
| Unbilled order book | RM61.2b | target was RM50b |
| New wins since Aug-25 | 21 projects, RM37.4b | big ramp-up |
| Share of order book not yet at peak | ~90% | execution risk is ahead, not behind |
| Net gearing | 72% | up from 53% |
| Operating cash flow | RM808m | on RM18.6b revenue |

Order book split: Malaysia RM26.3b (43%), Australia RM22.5b (37%), Taiwan RM10.7b (17%), Singapore RM1.7b (3%).

Key growth lines:
- **Data centres**: RM8.8b balance in Malaysia alone; RM3.57b of Port Dickson hyperscale wins in Aug-26; "more awards likely".
- **Renewable energy**: >5GW in development/construction (MY + AU). Proposed >680MWac CRESS hybrid solar + 4-hour BESS. A 33% JV signed a 21-year solar offtake with a US tech multinational, >RM10b total.
- **Recurring income assets**: 6 energy and water projects — Ulu Padas Hydro, BESS, Tasmania wind/solar, Hazelwood North, Northern Perak Water, CRESS hybrid.
- **Property pipeline**: RM9.7b FY27 launches across Vietnam, Singapore, Malaysia.

### The margin fact that matters

At a 3.1% overseas construction margin, **RM1 of cost saved equals about RM32 of new revenue**. In Malaysia, at 7.8%, RM1 saved equals about RM13 of revenue. Cost control beats order-book growth for profit, per ringgit of effort.

---

## 2. What Gamuda Tech already sells (do NOT rebuild these)

Gamuda Technologies is the external-facing digital arm. Nine products are public:

1. **Autonomous TBM AI Control System** — world-first, deployed MY/AU/SG.
2. **Tunnel Insight (TI) 3.0** — tunnelling data platform, MongoDB time-series.
3. **GDOS** — project management ecosystem; integrates Autodesk Forma, Oracle P6 EPPM, Candy, Moodle, SAP S4/HANA on GCP.
4. **Agentlinc** — internal knowledge/agent platform; drafting, summarising, research.
5. **Trudax** — AI answers over Power BI dashboards.
6. **SpatialQ** — no-code conversational geospatial analysis.
7. **GL Connect** — GenAI virtual sales agent for home buying (pre-sales only).
8. **BIMAR** — AR overlay of BIM models on site at 1:1.
9. **SIGMA** — ESG data management, geospatial environmental monitoring, SME sustainability.

Partners: Google Cloud, Gamuda DNeX Cloud (Google Distributed Cloud air-gapped), Autodesk, MongoDB, Cloud Space.
Stated sectors: construction, urban transport, national security, sustainability, talent. Also "defence technologies" and "new tech ventures".

Internal platform (from Zal's repos):
- **Odin** — GT agent harness. FastAPI, Postgres event log, multi-tenant, CherubLLM gateway (Claude/Gemini/wira), MCP tools, skills as markdown. First consumer: SpatialQ. Supersedes gt-agent-harness (Tunnel Insight).
- **financial-analysis** — LangGraph over Power BI/DAX, with WhatsApp and BigQuery integrations.

**Unfair advantage**: a hackathon team can ship an Odin consumer in hours. The conversation log, tool loop, streaming and prompt composition already exist.

---

## 3. White space — problems with no GT product

| # | Gap | Why it is money |
|---|---|---|
| A | Contract and claims administration (notices, variations, EOT) | Overseas margin is 3.1%. NEC/FIDIC/AS notice deadlines are the classic leak. |
| B | Progress claim → certification → cash | Net gearing 72%; operating cash is thin versus revenue. |
| C | Site safety in real time | Construction is Malaysia's deadliest sector. No GT product. |
| D | Automatic progress measurement | 77% of "sick" government projects come from weak planning and site coordination (Works Minister, Nov 2026). |
| E | Post-handover defects and the 24-month DLP | 5% retention held; 30-day repair rule; Tribunal claims to RM50,000. GL Connect stops at the sale. |
| F | Local authority approvals (OSC 3.0 Plus) | Target 21 days, 5 agencies. Real practice still slips. First-time-right submissions are rare. |
| G | Design-time embodied carbon + cost | NSRF Scope 3 reporting starts 2026. Hyperscaler clients demand low-carbon builds. SIGMA reports; it does not optimise design. |
| H | RE asset economics (solar + BESS dispatch over 21 years) | New recurring-income business. No tool covers bid or dispatch economics. |
| I | Non-revenue water for new water concessions | Gamuda now operates water assets (Rasau, Northern Perak). Malaysian NRW is roughly a third of supply. |

Rework benchmark for sizing: CII data puts direct field rework near 5% of construction value, 90th percentile 12.4%. Applied to RM61.2b, 1 point of rework is about RM600m. Treat as an estimate, not a Gamuda figure.

---

## 4. Facts vs beliefs

**Checked facts**: all FY26 financials, order book split, the nine GT products, the partner list, DLP rules, OSC 3.0 Plus targets, the data centre and RE wins.

**Beliefs (not checked)**: that Gamuda loses material money to missed contract notices; that site safety reporting is manual today; that defect handling after vacant possession is manual; that councils would pay for a submission checker. Each needs one internal conversation to confirm or kill.

**Unknown**: hackathon duration, team size, data access, judging panel.
