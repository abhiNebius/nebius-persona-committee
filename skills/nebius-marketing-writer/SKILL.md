---
name: nebius-marketing-writer
description: >
  Write any Nebius marketing artefact's copy to the house standard, using the
  Marketing Asset Library (18 asset-type playbooks distilled from 309
  competitor and hyperscaler excerpts). One writer for every asset type:
  homepage and hero, product or solution page, industry or M&E vertical page,
  customer case study, launch or announcement blog, benchmark post, technical
  deep-dive or cookbook, whitepaper or ebook, event page or event content,
  press release, pricing page, comparison page, paid ads (LinkedIn, Google,
  InMail), social posts, email or newsletter, partner or co-marketing, third-
  party validation (ClusterMAX, MLPerf), program page. Use whenever Abhishek
  asks to write, draft, rewrite or review one of these, or when /marketing
  reaches the copy-writing step. Routes PMM substance through PMM Sherpa,
  checks claims against the M&E Messaging Framework, lints the draft, and
  finishes with /writing-pass.
trigger: auto
auto_trigger_patterns:
  - case study
  - landing page
  - solution page
  - industry page
  - launch blog
  - press release
  - benchmark post
  - ad copy
  - linkedin post
  - event page
  - whitepaper
  - ebook
  - email sequence
  - newsletter
---

# Nebius Marketing Writer

One writer for every Nebius marketing asset. It turns what the market does well
into Nebius copy that is clear, evidence-led, additive and free of the
category's bad habits.

**Division of labour**
- **Claims and positioning** come from the M&E Messaging Framework and Copy Kit. Never from this skill or the library.
- **Form, structure and voice** come from `references/house-rules.md` and the matching playbook.
- **PMM substance** goes through PMM Sherpa (`draft_artifact`, `get_feedback`).
- **Layout** is handled by `/nebius-deck`, `/nebius-onepager` or `/nebius-doc`. **Final polish** is `/writing-pass`.

## Paths

- Library: `/Users/abhishekratna/Documents/AbhishekR/AbhishekR/Nebius/Marketing Asset Library/`
  - `Asset Type Playbooks/Playbook NN - <name>.md` (the skeletons)
  - `Excerpts by Competitor/` (raw verbatim evidence, only when you need more examples)
  - `00 Analysis - How AI Infrastructure Markets Itself (Sept 2026).md` (background thesis)
- Claims: `/Users/abhishekratna/Documents/AbhishekR/AbhishekR/Nebius/CURRENT Nebius M&E Messaging Framework - Refined 2026-09-09.md`, `CURRENT Nebius M&E External Copy Kit.md`, `M&E Messaging - Sources and Claim Notes.md`
- ClusterMAX digest: `/Users/abhishekratna/Documents/Claude Code/Knowledge Hub Markdown/External Artifact/semianalysis-clustermax-3.0-nebius-platinum-2026-09.md` (top digest only)
- Recent Nebius proof and launch history: `~/Documents/Claude Code/Nebius Blog Markdown/` (index: vault `Nebius/Nebius Blog Corpus.md`). Raw material only. Prefer the last 3 to 6 months.
- Lint: `scripts/lint_asset.py`

## Asset map

| NN | Asset type | Playbook file | Sherpa `artifact_type` |
|---|---|---|---|
| 01 | Homepage / hero | Playbook 01 - Homepage and Hero | `landing_page_copy` |
| 02 | Product or solution page | Playbook 02 - Product and Solution Pages | `landing_page_copy` |
| 03 | Industry / vertical page (M&E) | Playbook 03 - Industry and Vertical Pages (M&E) | `landing_page_copy` |
| 04 | Customer case study | Playbook 04 - Customer Case Studies | `case_study` |
| 05 | Launch / announcement blog | Playbook 05 - Launch and Announcement Blogs | `launch_blog_post` |
| 06 | Benchmark / performance post | Playbook 06 - Benchmark and Performance Posts | `blog_post_brief` |
| 07 | Technical deep-dive, docs, cookbook | Playbook 07 - Technical Deep-Dives and Docs-as-Marketing | `blog_post_brief` |
| 08 | Whitepaper / ebook / report | Playbook 08 - Whitepapers, Ebooks and Reports | `blog_post_brief` (outline), then native |
| 09 | Event / webinar / conference | Playbook 09 - Events and Conferences | `webinar_deck` for sessions; native for pages |
| 10 | Press release | Playbook 10 - Press Releases | `launch_press_release` |
| 11 | Pricing page | Playbook 11 - Pricing Pages | `pricing_page_copy` |
| 12 | Comparison / migration page | Playbook 12 - Comparison and Migration Pages | `comparison_matrix` |
| 14 | Paid ad | Playbook 14 - Paid Ads | `ad_copy_variants` |
| 15 | Social post | Playbook 15 - Social Posts | native (Sherpa `get_feedback` optional) |
| 16 | Email / newsletter | Playbook 16 - Email and Newsletters | `cold_email_sequence` |
| 17 | Partner / co-marketing | Playbook 17 - Partner and Co-Marketing | `joint_solution_brief` |
| 18 | Third-party validation | Playbook 18 - Third-Party Validation | native |
| 19 | Program page | Playbook 19 - Program Pages | `landing_page_copy` |

Type 13 (docs-as-marketing) uses Playbook 07. For a battlecard, one-pager or deck,
use Sherpa's `battlecard` / `one_pager_solution_brief` / deck types and the
matching layout skill. Pull form rules from the nearest playbook (a one-pager
borrows from 02 and 04).

## Workflow

### 1. Identify the asset and load the rules
- Map the request to one row above. If two fit (for example a launch post plus ads), write the primary one first, then derive the others from it.
- Read `references/house-rules.md` in full, every time.
- Read the playbook. Sections 3 (skeleton), 4 (headline formulas), 10 (Nebius rules) and 11 (inputs and lint) are mandatory. Read the rest when the asset is new to you.

### 2. Collect the inputs
Use the playbook's section 11 input list. At minimum:
- **Reader** (from the house-rules persona table) and **stage** (awareness, consideration, decision, procurement).
- **Workload and sub-vertical**: gaming, media-model makers (video, image, audio, world models), content production, ad tech, localization.
- **Proof available**: which cleared customer story, rating or benchmark. Check house-rules section 1. If the proof is not cleared, plan a placeholder. Do not go looking for a number to fill the gap.
- **CTA**: one approved purpose CTA.
- **Channel, length and destination**: web, PDF, deck, LinkedIn, email; where the file will live.

Ask Abhishek only for inputs you cannot find in the framework, Copy Kit, blog corpus or conversation. Otherwise pick the sensible default and state it.

### 3. Do the PMM thinking through Sherpa
- If the asset has a Sherpa `artifact_type`, call `mcp__pmm-sherpa__draft_artifact` with a `context` object carrying the product, company, audience, stage, workload, cleared proof (verbatim, with scope notes), the approved core copy, the chosen CTA, and the playbook skeleton. In `notes`, include the non-negotiables: no em-dashes, no invented metrics, additive not rip-and-replace, never "only" with Platinum, never Captions.
- Treat Sherpa's output as the substance draft. Then **re-fit it to the playbook skeleton** and the house rules. Sherpa does not know our evidence limits, so strip any number or customer it adds that house-rules section 1 does not carry.
- For native assets (no Sherpa type), draft straight to the skeleton.
- Never paste Sherpa's output as a labelled block. Never narrate the tool call.

### 4. Draft to the skeleton
- Follow the playbook's numbered skeleton and target lengths.
- Pick a headline formula from the playbook (section 4) or house rules (section 8).
- Open on the reader's workload or moment. Put the result in the first sentence where the asset has one.
- Tag every number inline with `[src: <cleared story or note>]` or a footnote `[^n]`. The tags stay in the working draft. Convert them to the channel's citation style (footnote, link, or removal for ads) only after lint passes.
- Use the additive template where the asset touches deployment.
- Leave `[bracketed placeholders]` for missing facts.

### 5. Lint
Run:
```
python3 ~/.claude/skills/nebius-marketing-writer/scripts/lint_asset.py <draft.md> --type NN
```
- Fix every ERROR. Resolve or justify every WARN (some are prompts to check context, such as a superlative with a cited source).
- Then work through the playbook's own section 11 lint checklist by hand. It has checks the script cannot run, such as whether a stat tile's baseline matches the story.
- Before delivery, run with `--final`. Open placeholders and unsourced metrics become errors. If a placeholder must ship to Abhishek for decision, say so and do not use `--final`.

### 6. Pressure-test (optional, for high-stakes assets)
For an M&E industry page, a press release, a flagship case study or a campaign, call `mcp__pmm-sherpa__get_feedback` once with the draft and the reader and stage. Apply what holds up against house rules. Ignore anything that would add unsourced claims.

### 7. Writing pass
Run `/writing-pass` on the near-final text. It edits prose, not claims. Re-run the lint after the pass.

### 8. Deliver
- Save the `.md` into the Obsidian vault in the folder that fits the work (M&E work goes under `Nebius/` or `Nebius/M&E Research/`). Rendered files (`.docx`, `.pdf`, `.pptx`) go to `/Users/abhishekratna/Documents/Nebius Artefacts/`.
- For a layout deliverable, hand the cleared copy to `/nebius-deck`, `/nebius-onepager` or `/nebius-doc`.
- In the hand-over message, list: the asset type and playbook used, the reader and stage, the proof used with sources, open placeholders and decisions, and the lint result.
- Never publish, post, send or upload without Abhishek's explicit approval in the current turn.

## Reviewing an existing asset
When asked to review rather than write: run the lint on the text (save it to the scratchpad first). For internal pieces that quote competitors (analyses, training material, team articles), add `--ignore-quotes` so quoted competitor copy is not flagged, and expect deliberate anti-pattern examples to remain. Compare it against the playbook skeleton and house rules. Optionally run Sherpa `get_feedback`. Return the highest-value fixes first, each naming the rule it serves.

## Non-negotiables (quick reference)
- No em-dashes. No invented metrics, customers, quotes, prices or dates.
- Additive, never displacement. Fill the additive template rather than saying "additive".
- ClusterMAX 3.0 Platinum, stated plainly, never "only". No ClusterMAX Gold.
- Neutrality only in the framework's narrow form. No TPN equivalence.
- Captions never. Reactor results not in public copy until cleared (Reactor as an agreed co-presenter is fine, with Reactor approval). Target accounts never shown as customers.
- Never reuse competitor copy. The excerpt banks are for study.

## Keeping the library current
The playbooks are dated 2026-09-28. Re-gather competitor assets every six months, or when a major competitor relaunches its site. When the framework or Copy Kit changes, update `references/house-rules.md` sections 1, 7 and 9 first.
