---
name: persona-committee
description: Run Nebius messaging past a synthetic buying committee of 11 evidence-based buyer personas (users such as Founder-CTO Farah and Inference Engineer Ingrid; buyers such as CFO Clara and CISO Cecil). Checks what Nebius has published (blog and press corpus plus nebius.com) and the live market with Tavily first, shows that brief for approval, then scores every message with every persona, runs a blind test against competitor copy and a Slack-style committee thread, and hands weak lines to the Nebius marketing writer for rewrites grounded in published proof, which the committee re-votes. Produces a Nebius-branded HTML report: the score (annotated asset and message grid), the conversation, the rewrites, then an appendix. Use when asked to test, pressure-test, review or get buyer feedback on messaging, a homepage, a landing page, a launch, an ad, a one-pager or any copy; or to "run the committee", "ask the personas" or "what would buyers think".
---

# Persona Committee

A buying committee you can call on any piece of Nebius messaging. It never replaces real buyers. It finds objections, unclear claims and me-too positioning before copy ships.

## What you need

- **Tavily key** in `TAVILY_API_KEY`. It is the only API key. Without it the run continues, and the report says "No live market check."
- **Claude Code or Codex**, logged in. Every model call runs through the host's own login.
- The persona library and competitor library paths in `~/.config/persona-committee/config.json` (defaults point at Abhishek's vault; see `config/config.example.json`).

## How to run it

All commands run from this skill's folder: `python3 scripts/committee.py ...`

### 1. Market Pulse (always first)
```
python3 scripts/committee.py pulse --asset <file | URL | ->
```
- Options: `--motion token_factory_sprint|capacity_deal|enterprise_relay|brand`, `--seat P01,P05,P07` (override the committee), `--engine codex`, `--pulse-from <run>` (reuse an earlier pulse for a fair before-and-after test).
- For pasted copy, save it to a scratch file first, or pipe it with `--asset -`.
- It prints the run name and the path of `pulse.md`.

### 2. Checkpoint: show the brief and wait
Read `pulse.md` and show the user, in a compact form:
- the committee that was seated;
- the claims under review;
- each live item (ID, one-line headline, source and date);
- competitor page changes.

Then ask: approve as is, strike items, or add an item. Do not continue until the user answers. Then run:
```
python3 scripts/committee.py edit-pulse <run> [--strike M3,M5] [--add "headline | url"]
```
Run `edit-pulse` with no options to approve as is. If the user said up front to skip the checkpoint, use `run` instead of `pulse` (it does every stage in one go).

### 3. The committee
```
python3 scripts/committee.py review <run> [--probe]
```
- Takes a few minutes: 11 private reviews in parallel, a debate, the judge, rewrites and a blind re-vote.
- `--probe` adds the flattery test (recommended for important assets).
- It prints the report path, the headline, the canary result and the status of each rewrite.

### 4. Hand over
- Give the user the report path (`report.html` in the run folder) and open it if they ask.
- Summarize in five lines or fewer: the verdict, the top and bottom message in the grid, the two biggest objections, and which rewrites were recommended or blocked. Mention any correction where a reviewer assumed something Nebius's own record contradicts.
- If the canary failed, say so first: the run was too agreeable and its praise should be discounted.

## Rules

- Never skip the checkpoint unless the user asked to.
- Never edit persona files or the competitor library from this skill. Those change only through the weekly refresh, with approval.
- The report is internal. Never publish, send or upload it without the user's explicit approval.
- Rewrites with `[bracketed placeholders]` need sourced facts before anything ships.
- State the limits when presenting results: synthetic personas, not calibrated against real buyers, and no call recordings or customer interviews behind them yet.

## What is inside

| Folder | Contents |
|---|---|
| `committee/` | The pipeline: pulse, review, debate, judge, rewrite, render, plus the engine (Claude Code or Codex) and Tavily client |
| `config/` | Defaults, persona seating and reading lists, competitor sets |
| `references/` | Scoring rubric and report style guide |
| `templates/` | The HTML report template |
| `scripts/committee.py` | The command line |
