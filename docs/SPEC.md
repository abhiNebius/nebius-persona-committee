# Persona Committee: Buildout Spec

Status: v1 spec, 2026-09-30. Owner: Abhishek Ratna (Nebius Marketing). Internal.

This spec covers the whole buildout. Phase 1 is being built now. Later phases are specified here so the design holds together, and are built after the Oct 8 marketing all-hands.

## 1. The problem

Marketing ships messaging without a fast, repeatable way to hear how real buyers would react. Two custom GPTs (AI Builder, AI Buyer, Sep 22) proved the idea but hit limits:

- One model plays one persona in one chat. Research shows a single model playing several characters drifts and blurs them together, so a real committee cannot be simulated.
- Knowledge files are static. The personas never learn what happened in the market this month.
- There is no competitor comparison, no scoring, no report and no way to distribute to other teams except by sharing a GPT link.

## 2. The product

`persona-committee`: a skill for Claude Code and Codex. You hand it a piece of messaging (a draft, a file or a URL). It:

1. Checks the live market (Tavily) for what changed in each buyer's world in the last 30 days and what competitors said in the last 90, and shows you that brief before any feedback starts.
2. Seats the right buying committee from 11 evidence-based personas.
3. Has each persona review the copy privately, including a blind side-by-side against competitor copy.
4. Runs a moderated debate between the personas.
5. Scores and ranks the result, with users voting first and buyers holding a veto on credibility.
6. Hands the weak lines to the Nebius marketing copywriter (`nebius-marketing-writer`) for rewrites, then has the committee re-vote blind.
7. Writes a Nebius-branded HTML report in plain, journalistic English.

No custom GPTs. Distribution is the skill folder, installed into Claude Code (`~/.claude/skills/`) or Codex (`~/.codex/skills/`).

## 3. Decisions log

| # | Decision | Date |
|---|---|---|
| D1 | Committee is a skill, not a GPT. Package for Claude Code and Codex. GPTs are retired from the roadmap | 2026-09-30 |
| D2 | Runs without PMM Sherpa | 2026-09-30 |
| D3 | Only one API key: Tavily. No Firecrawl. Everything else uses the host tool's own login (Claude Code or Codex) | 2026-09-30 |
| D4 | News window 30 days; competitor messaging window 90 days | 2026-09-30 |
| D5 | Checkpoint: the Market Pulse is shown for review before feedback, by default | 2026-09-30 |
| D6 | Forum sentiment (Hacker News, Reddit) is included, labeled as sentiment, never as fact | 2026-09-30 |
| D7 | Blind side-by-side test against competitor copy is on by default | 2026-09-30 |
| D8 | Users vote first on resonance. Buyers hold a veto on credibility | 2026-09-30 |
| D9 | Report is HTML in Nebius colors. Page order: 1 Pulse and scorecard, 2 Dialog, 3 Ranking, 4 Competitive view, 5 Proposed messaging changes | 2026-09-30 |
| D10 | Weekly refresh for personas and the competitor library. All edits to vault notes are proposals that need approval | 2026-09-30 |
| D11 | Persona names are role plus name (Founder-CTO Farah and so on). Users P01 to P06, buyers P07 to P11 | 2026-09-30 |
| D12 | Nebius has no call recordings or customer interview corpus. This is stated as a known gap everywhere the personas are presented | 2026-09-30 |
| D13 | The report is written for busy marketers: short sentences, literal competitor excerpts instead of abstract patterns, plain criteria names | 2026-09-30 |
| D14 | Every link the market sweep finds is kept: a sources section in the report, `sources.csv` per run, and a cross-run `sources-ledger.csv` | 2026-09-30 |
| D16 | A Nebius fact sweep (local blog and press corpus plus nebius.com via Tavily) runs before every review; nothing in the report may contradict it | 2026-09-30 |
| D17 | Report is three parts: the score (annotated asset, message-by-persona grid, pillar coverage), the conversation (Slack-style), the rewrites (grounded in Nebius-published proof). Everything else is a collapsible appendix | 2026-09-30 |
| D18 | Grade the value-pillar messaging, not only technical claims | 2026-09-30 |
| D15 | Package both skills (`persona-committee`, `nebius-marketing-writer`) in one private GitHub repo with an install script for Claude Code and Codex | 2026-09-30 |

## 4. Architecture

```
asset (text, file or URL)
   |
   v
[0] MARKET PULSE ---- Tavily search (per-persona sources, 30 days)
   |                  Tavily search (competitor news, 90 days)
   |                  Tavily extract (competitor pages matching the asset type)
   |                  Marketing Asset Library (309 excerpts, baseline)
   v
 CHECKPOINT (you strike, add or approve items)
   |
   v
[1] PRIVATE REVIEWS -- one isolated model call per seated persona
   |                   fixed identity (persona file) + "this week in your world"
   |                   + blind Vendor A/B/C test
   v
[2] DEBATE ---------- moderator picks 3 points; personas reply in turn,
   |                   seeing earlier replies anonymized
   v
[3] JUDGE ----------- code computes scores, ranking, vetoes, canary, blind result
   |                   model writes the verdict, overlap map, recommendations
   v
[4] REWRITE --------- nebius-marketing-writer rules + playbook + linter
   |                   committee re-votes blind (max 2 rounds)
   v
[5] REPORT ---------- HTML, 5 pages + method appendix
```

Each model call is a separate process (`claude -p` or `codex exec`), so personas never share a context. Calls run in parallel.

## 5. Components

| Component | File | Job |
|---|---|---|
| Config | `committee/config.py` | Loads `~/.config/persona-committee/config.json`, falls back to the example |
| Engine | `committee/engine.py` | One function to run a prompt with a JSON schema on Claude Code or Codex. Lean mode (no tools, no user settings) for persona calls |
| Personas | `committee/personas.py` | Parses the 11 persona files: frontmatter, agent block, concerns, reading habits, voice |
| Library | `committee/library.py` | Parses the competitor excerpt files into entries (company, URL, asset type, verbatim lines) |
| Tavily | `committee/tavily.py` | Search and extract over HTTP, with a per-run budget and a 24-hour cache |
| Pulse | `committee/pulse.py` | Claim extraction, search plan, live page checks, grading into M-items, the brief |
| Review | `committee/review.py` | Seating, private reviews, blind test, canary, optional sycophancy probe |
| Debate | `committee/debate.py` | Moderator and turn-taking |
| Judge | `committee/judge.py` | Deterministic scoring plus the written verdict; verifies every competitor excerpt is verbatim |
| Rewrite | `committee/rewrite.py` | Writer call, lint, copy-overlap check, number check, blind re-vote |
| Render | `committee/render.py` + `templates/report.html` | The HTML report |
| CLI | `scripts/committee.py` | `pulse`, `edit-pulse`, `review`, `run`, `render`, `status` |

## 6. Scoring

Five criteria, 1 to 7, each with written anchors (`references/rubric.md`). Report labels are plain English:

| Internal key | Report label | Question |
|---|---|---|
| `jtbd` | Fits their job | Does it speak to the job they are trying to get done? |
| `credible` | Believable | Would they believe it, and could they check it? |
| `emotional` | Meets the feeling | Does it address what they fear or want to feel? |
| `different` | Stands out | Is it different from what competitors say? |
| `clear` | Clear | Can they tell what is being offered, to whom, in one read? |

Rules computed in code, not by a model:
- **Persona score** = mean of the five criteria.
- **Ranking** = users first (P01 to P06), then buyers (P07 to P11), each sorted by score.
- **Veto** = a buyer marks a claim "fails" and either scores Believable 3 or lower or declines the meeting. A vetoed claim cannot be recommended as is.
- **Canary** = one deliberately weak line is slipped into every claim list. If a majority of the committee does not mark it weak or failing, the run is flagged "panel may be too agreeable".
- **Blind result** = Nebius's average rank among vendors, how many personas would take the Nebius meeting, and how many could not tell Nebius apart from a competitor.
- **Re-vote** = users decide which version wins; any buyer who marks the new version not believable blocks it.

## 7. Guardrails

- **No invented facts.** Personas cite live items only by ID (M1, M2). The writer may only use numbers found in the claims sources or the original copy; anything else stays in `[brackets]`. Code checks every digit in a rewrite.
- **No copied competitor copy.** Rewrites are checked for any run of 6 or more words shared with competitor text.
- **Excerpts are verbatim.** Every competitor quote in the report is checked, in code, against the text it came from. Paraphrases are dropped.
- **Web text is data, not instructions.** Fetched pages are wrapped and labeled untrusted in every prompt.
- **Honest failure.** If Tavily is unavailable the run continues with a banner: "No live market check."
- **Budget.** At most 25 Tavily calls per run; results cached for 24 hours; the run log records spend.
- **Reproducible.** Every run saves its pulse, reviews and prompts. `--pulse-from <run>` reuses a pulse for fair before-and-after comparisons.
- **Internal only.** Reports cite internal deal evidence through the persona files. Nothing leaves the building without sign-off.

## 8. Report

Written to the standard in `references/report-style.md`: a top journalist writing for a busy marketer. Short sentences. The point first. Real examples and literal excerpts. No unexplained jargon.

| Page | Contents |
|---|---|
| 1 | Verdict in one sentence. "What changed this month" strip. Scorecard grid (users, then buyers) |
| 2 | The committee dialog: speech bubbles, the persona's name under each bubble with the role in italics, source chips for live items, score changes called out. Each persona's key recommendation |
| 3 | Ranking, veto badges, canary result |
| 4 | Competitive view: blind test in plain words, claim-by-competitor overlap with literal excerpts and links, what changed on competitor pages, patterns worth borrowing shown as real examples |
| 5 | Proposed messaging changes: before and after, why, who it answers, the example it borrows from, evidence, open placeholders, scores before and after |
| Appendix | Method, sources, limits (including no call recordings), run details |

## 9. Phases

| Phase | Scope | Done when | Status |
|---|---|---|---|
| **1. Committee skill** | Everything in sections 4 to 8 | A full run on the Nebius homepage produces a 5-page report; canary rejected; lint passes; no unverified excerpt | Building now |
| **2. Demo assets** | Committee deck via `nebius-deck` (one slide per persona: icon, job, needs, pains, how to message, titles; users first; sources; "why it's credible"). Project one-pager via `nebius-onepager` | Both render cleanly and pass visual QA | Before Oct 8 |
| **3. Weekly refresh** | `persona-refresh` launchd job (section 10) | Two clean weekly runs reviewed | After Oct 8 |
| **4. Calibration** | Held-out objection test: hide 30% of real objections, check the committee raises 70% unprompted | Result recorded per persona | After Oct 8 |
| **5. Real buyer truth** | Call recording setup and user interviews, win/loss sprint | First real transcripts in the evidence layer | Needs a recording tool and security review |
| **6. Vertical overlays** | Industry overlays on the 11 personas, M&E first | M&E overlay runs on an M&E asset | Later |
| **7. Distribution** | Private GitHub repo, install script, team rollout | A second person installs and runs it | Later |

## 10. Weekly refresh (Phase 3 design)

Pattern: the Daily Sweep (launchd + headless run + prompt file + state file).

- **Where:** `~/.claude/persona-refresh/` with `run-refresh.sh`, `refresh-prompt.md`, `state.json`.
- **When:** Mondays 5:30am PT, launchd job `com.abhishek.persona-refresh`.
- **Inputs:**
  1. The past week's Market Pulse files from every committee run.
  2. A fresh Tavily sweep of each persona's reading list (the same source map the pulse uses), 7-day window.
  3. The week's Daily Sweep notes (internal deal signals), read only for Nebius context.
  4. A re-fetch (Tavily extract) of every competitor URL in the Marketing Asset Library.
- **Persona drift rules.** Propose a persona edit when:
  - an item marked "new" appears in two or more runs or sources that week;
  - an item contradicts a statement in a persona file;
  - a concern in a persona file has had no supporting signal for 90 days (marked "possibly stale");
  - a title or tool is rising in job postings (optional source).
- **Competitor drift rules.** Propose a library update when a tracked page's headline, tagline, pricing or proof block changed, or a new launch appeared. Store the new verbatim excerpt alongside the old one with both dates.
- **Output:** a Persona Changelog note and a Competitor Changelog note in the vault, each edit shown as before, after and evidence. A short Slack DM summary.
- **Human gate:** nothing in the vault changes until Abhishek approves. Approved edits bump `last_verified` in the persona frontmatter.

## 11. Out of scope for Phase 1

Weekly refresh automation, calibration, call recordings, vertical overlays, GitHub sync, the deck and one-pager (Phase 2), and any custom GPT work.

## 12. Known limits

- Personas are composites built from 334 public and internal quotes. They are not calibrated against live buyers.
- Nebius has no call recordings or customer interview corpus. The strongest possible grounding source does not exist yet.
- Synthetic panels are good at finding objections and weak at predicting which message wins. The report says so on every run.
