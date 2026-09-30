# Nebius Marketing House Rules

Loaded for EVERY asset, before the playbook. Distilled from the Marketing Asset Library analysis (309 competitor excerpts, 2026-09-28) and the current M&E Copy Kit. Where anything here conflicts with the Messaging Framework or Copy Kit, those win on claims; these rules win on form and voice.

## 1. Where claims come from

- **Positioning and claims:** `CURRENT Nebius M&E Messaging Framework - Refined 2026-09-09.md`. **Approved copy and CTAs:** `CURRENT Nebius M&E External Copy Kit.md`. **Claim scope:** `M&E Messaging - Sources and Claim Notes.md`. All in `/Users/abhishekratna/Documents/AbhishekR/AbhishekR/Nebius/`.
- Nothing in the Marketing Asset Library is a source for a Nebius claim. Competitor quotes are for study only and are never reused as Nebius copy.
- **Cleared M&E customer proof (framework section 7).** Always carry the scope note:

| Customer | Usable proof | Scope note to carry |
|---|---|---|
| Recraft V4 | Hopper to Blackwell with minimal code changes; Recraft reports 350M+ cumulative images | Platform figure, not a Nebius guarantee |
| Recraft (foundational model) | 4x fabric throughput and approximately 6x faster training after specific corrections, 20B-parameter image model | "after the specific corrections" |
| Higgsfield | First training run started in under an hour; Higgsfield reports 4.5M+ daily generations | Platform figure |
| Krisp | 50 to 80% faster training versus its familiar A100 baseline; data transfer and training started within a day | Baseline is A100; final models run on devices |
| Wubble | 3B+ parameter music model, 100+ genres; reported 1.8-second time to first token; integrated with its GCP environment | TTFT is not full-song generation time |
| Photoroom | Reports 3x inference speed and 300 TB of storage | Public reference does not specify the comparison configuration |
| Dubformer | Broadcast-quality localization in 70+ languages | |
| Chatfuel | One month to production; three days for SDK integration | Engagement, not a game studio |

- **Reactor:** the case-study draft and its results (streaming latency, GPU cost versus a hyperscaler) stay out of public copy until publication clearance. Reactor may be named as a co-presenter or partner in assets Reactor itself has agreed to (for example the joint October 2026 webinar), with Reactor approving every line about Reactor and every attributed quote.
- **Captions:** closed-lost. Never appears in any Nebius asset, even as an example.
- **Gaming:** the current set does not establish gaming moderation, matchmaking or QA outcomes on Nebius. Treat game-AI uses as platform applications, not proven deployments.
- **Archived IDs:** E1 to E8 (from the pre-2026-09-16 register) may be used as internal shorthand. E9 to E16 (Shopify, Ultimate Bots, TheStage AI, Wildflow, Lynx Analytics, Voxel51, SGLang, Brave/vLLM) are non-M&E and not allowed in M&E assets.
- **Target accounts** (e.g. Black Forest Labs, Runway, World Labs) are never shown as customers.
- If a needed fact is missing, write a bracketed placeholder: `[metric from cleared customer story]`. Never invent a metric, customer, quote, price or date.

## 2. Standing claim rules

- **ClusterMAX 3.0:** "Nebius is rated Platinum in SemiAnalysis ClusterMAX 3.0 (September 2026)." Say what the test measured. Never "only", "one of the only", or a ranking above CoreWeave. Link `nebius.com/blog/posts/nebius-platinum-clustermax-3-0`, never the paywalled article. "ClusterMAX Gold" is stale everywhere.
- **Neutrality:** only in the framework's narrow form: "a provider without a competing studio or proprietary media-model business." Never "no models", "never compete", or claims about how competitors treat customer content.
- **Protection:** match to documented controls, services and regions. No absolute safety, automatic compliance or unqualified residency.
- **TPN:** Nebius does not hold TPN Gold Shield. No equivalence claims.
- **Comparisons:** tied to their reported baseline and dated. No universal cost, uptime, latency, capacity or egress advantage.
- **"First", "only", "largest", "fastest":** only with a linked partner or third-party source and an "as of" date.

## 3. Additive, made concrete

Nebius is added alongside existing clouds, owned GPUs and model APIs. Never rip-and-replace. Do not merely say "additive" (every competitor now does). Fill the template:

> **We add [workload] when [condition], measured by [metric against the customer's baseline, from a cleared story].**

Conditions buyers name: a training run exceeds contracted capacity; a launch or viral spike needs same-day serving; a new model starts greenfield; a production queue peaks around a schedule.

Closing copy (approved): "Start with one model or production workload. Define the performance, cost and control requirements, then evaluate Nebius against them."

**Banned displacement language:** "chose us over", "switched from", "migrated away", "replace your cloud", "rip and replace", "hyperscalers fell short", "GPUs retired", "hyperscalers cannot".

## 4. Proof hierarchy (use the highest tier available)

1. Named customer + one number against their own baseline + the mechanism.
2. Buyer voice in public (quote in a story, release, panel or post). Secure it before writing.
3. Independent rating or verified benchmark, with the method explained (ClusterMAX Platinum, verified MLPerf).
4. Honesty devices: "what we learned", a limit, a dated comparison.
5. NVIDIA partnership facts, stated plainly, never the main proof.
6. Scale and capacity facts, only with a source.

Every number carries **unit, baseline, date, and source**. In drafts, tag each with `[src: <story or note>]` or a Markdown footnote `[^n]`. The lint script checks this.

**Never:** "up to" without a baseline; unnamed-competitor charts; vendor-borrowed multipliers; numbers that differ from our other assets.

## 5. Proof by reader (hypothesis; validate against the persona set)

| Reader | Lead proof | Lead CTA |
|---|---|---|
| Model-maker founder or CEO | Named peer story, time to production | Plan capacity for your next training run. |
| ML or infra lead | Verified benchmark, ClusterMAX, co-engineering detail | Benchmark your game AI or media workload. |
| Studio CTO or tech lead | Additive template, protection controls, architecture | Review your IP and data-protection requirements. |
| Product or creative lead | Creative-unit numbers (per clip, per image, per minute) | Evaluate your model-serving deployment. |
| Finance | Baseline-to-result numbers, capacity options | Plan capacity for your next training run. |

## 6. Voice

**Do**
- Open on the reader's workload or moment, not on Nebius.
- Result in the first sentence of any case study, benchmark or launch.
- Specific nouns and verbs: train, adapt, serve, batch, queue, asset, weights, run.
- Creative units for gen-media readers: per clip, per second of video, per image, per audio minute, per accepted asset, per finished minute of content.
- Promise in the headline, proof directly beneath it.
- Short sentences for emphasis. Vary length.

**Do not**
- Clichés: purpose-built, at scale, pilot to production, experimentation to production, unlock, supercharge, next-generation, cutting-edge, seamless, game-changing, revolutionize, leverage, best-in-class, world-class, unmatched, unparalleled, industry-leading.
- Coined terms not already in the framework (competitors live on "goodput", "AI superfactory", "Frontier Firm"; we do not).
- Leading with table stakes: "full-stack", "vertically integrated", "no egress fees", uptime and SOC 2 rows.
- Slang or emoji.
- Childlike simplification. Clear is not simplistic.

**Punctuation.** No em-dashes, ever. Colon to explain, period to land a point, comma for rhythm, parentheses for an aside.
- Before: "The era of AI experimentation is over -- production-grade execution is here."
- After: "The era of AI experimentation is over. Production is here."

## 7. Approved core copy (Copy Kit, verbatim)

- Category: **The AI cloud for media and entertainment.**
- Pillars: **Build faster. Scale with confidence. Own your intelligence.**
- Proposition: **Build game AI, train demanding media models and run creative workflows on neutral infrastructure that protects your IP.**
- Optional creative headline: **Bring your most creative vision to life.** (Always beside the concrete proposition.)

## 8. Headline formulas

| Formula | Use |
|---|---|
| Plain three-beat | "Build faster. Scale with confidence. Own your intelligence." |
| Named customer + one number | "[Customer] [verb] [cleared metric vs baseline] on Nebius" |
| Workload + promise | "The AI cloud for media and entertainment." |
| Reader's question | "What does your next training run need?" (validate before use) |
| Avoid: qualifier game | Not "Still the only one." Use "Platinum-rated in SemiAnalysis ClusterMAX 3.0." |

## 9. CTAs

Approved purpose CTAs (Copy Kit section 8):
- Benchmark your game AI or media workload.
- Plan capacity for your next training run.
- Evaluate your model-serving deployment.
- Review your IP and data-protection requirements.

Platform or logistics button labels ("Book a meeting", "Watch now", "Register") are allowed when an approved CTA states the purpose nearby.

| Stage | Nebius choice |
|---|---|
| Awareness (ads, social, events) | Content offer or event meeting |
| Consideration (industry, product, case study) | Benchmark your game AI or media workload. |
| Decision (pricing, comparison, evaluation) | Plan capacity / Evaluate your model-serving deployment. |
| Security and procurement | Review your IP and data-protection requirements. |

## 10. Competitor facts safe to use internally

These inform framing. Do not attack competitors by name in external copy.
- CoreWeave markets ClusterMAX as "Three-time Platinum. Still the only one." and never names the second Platinum provider.
- fal named AWS its preferred cloud provider (May 2026).
- NVIDIA's IBC and NAB 2026 M&E co-marketing names only AWS.
- Crusoe uses "burst capacity" language close to ours; our difference is training through inference plus co-engineering.
