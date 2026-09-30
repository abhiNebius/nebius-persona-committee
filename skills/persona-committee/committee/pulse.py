"""Stage 0: the Market Pulse. Runs before any persona speaks.

1. Break the asset into numbered claims (plus one hidden canary line).
2. Search where each seated persona actually reads (30 days) and competitor newsrooms (90 days).
3. Fetch the competitor pages that match this asset type and compare them with the library snapshot.
4. Grade everything into short, dated, sourced items (M1, M2 ...) and write the checkpoint brief.
"""
import random

from . import nebius as NB
from . import personas as PS
from .tavily import tier
from .util import arr, b, clean, norm, obj, s, today, untrusted, write_json

ASSET_TYPES = ["01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12", "14", "15", "16", "17", "18", "19"]
PRODUCT_LINES = ["token_factory", "ai_cloud", "enterprise", "brand"]
MOTIONS = ["token_factory_sprint", "capacity_deal", "enterprise_relay", "brand"]

CANARIES = [
    "We deliver seamless, world-class AI infrastructure that unlocks limitless innovation for every business.",
    "Next-generation performance and unmatched value, purpose-built for the future of AI.",
    "The most powerful, most flexible, most trusted AI platform on the planet.",
]

CLAIMS_SCHEMA = obj(
    title=s("Short name for the asset, e.g. 'Nebius homepage hero'"),
    asset_type=s("Playbook id", enum=ASSET_TYPES),
    product_line=s(enum=PRODUCT_LINES),
    motion=s(enum=MOTIONS),
    summary=s("One plain sentence: what this asset is trying to say"),
    claims=arr(obj(text=s("The message, in the asset's own words"),
                   label=s("Two to four words naming the element, e.g. 'Hero headline', 'Reliability stat', 'Pillar: Predictable'"),
                   part=s(enum=["headline", "subhead", "pillar", "proof", "body", "cta"]),
                   pillar=s(enum=["build_faster", "scale_with_confidence", "own_your_intelligence", "none"]),
                   kind=s(enum=["number", "superlative", "capability", "positioning", "proof", "cta"]))),
    topics=arr(s("A 3 to 7 word web search phrase about the market topic, no vendor names")),
    competitors_named=arr(s()),
)

GRADE_SCHEMA = obj(
    items=arr(obj(
        ref=s("The R id of the search result this item is based on"),
        kind=s(enum=["trend", "claim_check", "competitor_move", "sentiment"]),
        headline=s("One plain sentence saying what happened, with who and when"),
        why_it_matters=s("One sentence: why this matters for the asset's claims"),
        persona_ids=arr(s()),
        claim_ids=arr(s()),
        drift=s(enum=["confirms", "new", "stale", "none"]),
    )),
    competitor_changes=arr(obj(
        company=s(), url=s(),
        change=s("One plain sentence on what differs from the library snapshot, or 'No material change'"),
        new_line=s("A line copied exactly from the live page text that shows the change", nullable=True),
    )),
    claim_checks=arr(obj(
        claim_id=s(),
        status=s(enum=["holds", "contested", "outdated", "unverified"]),
        note=s("One plain sentence"),
        ref=s(nullable=True),
    )),
)


def extract_claims(engine, asset_text):
    system = ("You are a senior product marketing editor. You break marketing copy into its message units: the headline, "
              "the subhead, each value pillar and the line that carries it, the proof points and the call to action. Grade the "
              "messaging, not only the technical claims. Tag each unit with the Nebius value pillar it serves: build_faster "
              "(dev-first, frontier-ready platform), scale_with_confidence (predictable capacity, performance and economics), "
              "own_your_intelligence (open-model choice and full-stack control), or none. "
              "Copy each claim using the asset's own words. A number shown apart from its caption (a stat tile such as "
              "'43%' above 'better TCO for inference vs. AWS') is one claim: join them as '43% better TCO for inference vs. AWS'. "
              "Never list a bare number on its own. Keep at most 10, most important first. "
              "Skip navigation, legal text and repeated lines. Choose the asset type from these playbook ids: "
              "01 homepage/hero, 02 product or solution page, 03 industry page, 04 case study, 05 launch blog, "
              "06 benchmark post, 07 technical post, 08 whitepaper, 09 event, 10 press release, 11 pricing page, "
              "12 comparison page, 14 paid ad, 15 social post, 16 email, 17 partner, 18 third-party validation, 19 program page. "
              "Motion: token_factory_sprint (inference API buyers), capacity_deal (GPU clusters), "
              "enterprise_relay (large regulated companies), brand (company-wide, mixed audiences).")
    out = engine.run(system, "ASSET:\n\n" + asset_text[:20000], CLAIMS_SCHEMA, tier="deep", label="pulse:claims")
    claims = [c for c in out["claims"] if c["text"].strip()][:10]
    canary = random.choice(CANARIES)
    pos = random.randint(1, max(1, len(claims)))
    claims.insert(pos, {"text": canary, "kind": "superlative", "label": "Supporting line", "part": "body", "pillar": "none"})
    for n, c in enumerate(claims, 1):
        c["id"] = f"C{n}"
    out["claims"] = claims
    out["canary_id"] = claims[pos]["id"]
    return out


def _persona_query(cfg, meta, p):
    pc = cfg["personas_cfg"]
    lens = pc.get("lens", {}).get(p.pid, "")
    term = pc.get("line_terms", {}).get(meta["product_line"], "AI cloud")
    return f"{lens} {term}".strip()


def gather(cfg, tav, lib, people, seat, meta):
    """Runs the searches and page fetches. Returns raw results and live competitor texts."""
    t = cfg["tavily"]
    ccfg = cfg["competitors_cfg"]
    comps = ccfg["sets"].get(meta["product_line"], ccfg["sets"]["brand"])
    comp_domains = [ccfg["companies"][c]["domain"] for c in comps if c in ccfg["companies"]]
    results, seen_queries = [], set()

    # 1. per-persona reading lists, 30 days
    for pid in seat:
        p = people[pid]
        q = _persona_query(cfg, meta, p)
        key = (q, tuple(p.sources))
        if key in seen_queries:
            continue
        seen_queries.add(key)
        for r in tav.search(q, days=t["news_days"], domains=p.sources, topic="news", max_results=5):
            r["for"] = [pid]
            results.append(r)

    # 2. the market at large, 30 days (claim check)
    for r in tav.search((meta.get("topics") or [meta["summary"]])[0], days=t["news_days"], topic="news", max_results=8):
        r["for"] = list(seat)
        results.append(r)

    # 3. competitor newsrooms and blogs, 90 days
    q = cfg["personas_cfg"].get("line_terms", {}).get(meta["product_line"], "AI cloud") + " launch announcement"
    for r in tav.search(q, days=t["competitor_days"], domains=comp_domains, topic="general", max_results=8):
        r["for"], r["competitor"] = list(seat), True
        results.append(r)

    # 4. live competitor pages that match this asset type
    pages = []
    for c in comps:
        e = lib.best(c, meta["asset_type"])
        url = e.url if e and e.url.startswith("http") else ccfg["companies"].get(c, {}).get("homepage")
        if url:
            pages.append({"company": c, "url": url, "entry": e})
    live = tav.extract([p_["url"] for p_ in pages])
    for p_ in pages:
        text = live.get(p_["url"]) or ""
        p_["live_text"] = text
        e = p_["entry"]
        if e and text:
            kept = [ln for ln in e.lines if norm(ln)[:60] in norm(text)]
            p_["kept"], p_["total"] = len(kept), len(e.lines)
            p_["missing"] = [ln for ln in e.lines if ln not in kept][:4]
        else:
            p_["kept"], p_["total"], p_["missing"] = 0, len(e.lines) if e else 0, []

    # de-duplicate by URL, merge persona tags
    by_url = {}
    for r in results:
        if r["url"] in by_url:
            by_url[r["url"]]["for"] = sorted(set(by_url[r["url"]]["for"]) | set(r["for"]))
        else:
            by_url[r["url"]] = r
    merged = list(by_url.values())
    for n, r in enumerate(merged, 1):
        r["id"] = f"R{n}"
        r["tier"] = tier(r["domain"], cfg, comp_domains)
    return merged, pages, comps


def grade(engine, cfg, people, seat, meta, results, pages, facts_text="none"):
    claims = "\n".join(f"{c['id']}: {c['text']}" for c in meta["claims"] if c["id"] != meta["canary_id"])
    roster = "\n".join(f"{pid} {people[pid].display}: {people[pid].tagline}" for pid in seat)
    res = "\n\n".join(
        f"{r['id']} | {r['domain']} | tier {r['tier']} | {r['date'] or 'within ' + str(r['window_days']) + ' days'} | for {','.join(r['for'])}\n"
        f"TITLE: {r['title']}\n" + untrusted(r["url"], r["snippet"]) for r in results)
    comp = "\n\n".join(
        f"{p_['company']} | {p_['url']} | library lines still live: {p_['kept']} of {p_['total']}\n"
        f"LIBRARY LINES NOT FOUND LIVE: {p_['missing']}\n" + untrusted(p_["url"], (p_["live_text"] or "")[:2500])
        for p_ in pages)
    system = (
        "You are a market-intelligence editor preparing a short brief for a buying committee that will review a "
        "piece of Nebius marketing. Pick only items that a real buyer in the named roles would notice this month "
        "and that bear on the asset's claims. Every item must point to one R id. Never invent facts, dates or numbers "
        "beyond what the results say. Tier 3 results (forums) are sentiment, never fact: use kind 'sentiment'. "
        "Drift: 'confirms' if it supports a concern the role already has, 'new' if it is a concern the role likely "
        "does not have yet, 'stale' if it shows a concern has faded. Write in short, plain sentences. No em-dashes. "
        f"Return at most {cfg['pulse']['items_per_persona']} items per persona and at most 18 items in total. "
        "For competitor pages, say plainly whether the messaging changed since the library snapshot (Sept 28). "
        "new_line must be copied exactly from the live page text, or null. For claim checks, cover each claim. "
        "VERIFIED NEBIUS FACTS are what Nebius has published. Never write anything that contradicts them, and never say "
        "Nebius lacks something they show it has. If a claim is supported by them, the status is 'holds'; if the asset simply "
        "omits a published proof, say the page does not show it.")
    prompt = (f"ASSET: {meta['title']} ({meta['summary']})\n\nCLAIMS:\n{claims}\n\nCOMMITTEE:\n{roster}\n\n"
              f"VERIFIED NEBIUS FACTS:\n{facts_text}\n\n"
              f"SEARCH RESULTS:\n{res or 'none'}\n\nCOMPETITOR PAGES:\n{comp or 'none'}")
    return engine.run(system, prompt, GRADE_SCHEMA, tier="deep", label="pulse:grade")


def build(cfg, engine, tav, lib, people, asset_text, source_label, motion=None, seat_override=None):
    meta = extract_claims(engine, asset_text)
    if motion:
        meta["motion"] = motion
    seat = PS.seat(people, cfg, meta["motion"], meta["asset_type"], seat_override)
    facts = NB.sweep(cfg, engine, tav, meta)
    pulse = {"date": today(), "source": source_label, "meta": meta, "seat": seat, "nebius": facts,
             "live_check": tav.available, "items": [], "competitor_changes": [], "claim_checks": [],
             "competitors": [], "pages": [], "results": []}
    if not tav.available:
        pulse["banner"] = "No live market check: TAVILY_API_KEY is not set. Feedback uses the persona files only."
        return pulse
    results, pages, comps = gather(cfg, tav, lib, people, seat, meta)
    pulse["competitors"] = comps
    pulse["results"] = results
    pulse["pages"] = [{k: v for k, v in p_.items() if k != "entry"} | {"entry_id": p_["entry"].eid if p_["entry"] else None,
                       "library_date": p_["entry"].date if p_["entry"] else None} for p_ in pages]
    if not results and not any(p_["live_text"] for p_ in pages):
        pulse["banner"] = "Live market check returned nothing: " + "; ".join(tav.errors[:2])
        return pulse
    g = grade(engine, cfg, people, seat, meta, results, pages, NB.brief(facts))
    ref = {r["id"]: r for r in results}
    live_texts = {p_["url"]: p_["live_text"] for p_ in pages}
    per = {}
    for it in g["items"]:
        r = ref.get(it["ref"])
        if not r:
            continue  # an item must trace to a real result
        pids = [x for x in it["persona_ids"] if x in seat] or r["for"]
        if all(per.get(x, 0) >= cfg["pulse"]["items_per_persona"] for x in pids):
            continue
        for x in pids:
            per[x] = per.get(x, 0) + 1
        pulse["items"].append({"id": f"M{len(pulse['items']) + 1}", "kind": it["kind"], "headline": it["headline"],
                               "why": it["why_it_matters"], "persona_ids": pids, "claim_ids": it["claim_ids"],
                               "drift": it["drift"], "url": r["url"], "source": r["domain"], "date": r["date"],
                               "window_days": r["window_days"], "tier": r["tier"], "origin": "tavily"})
    for c in g["competitor_changes"]:
        nl = c.get("new_line")
        if nl and norm(nl)[:80] not in norm(live_texts.get(c["url"], "")):
            c["new_line"] = None  # drop anything not copied exactly
        pulse["competitor_changes"].append(c)
    pulse["claim_checks"] = [cc for cc in g["claim_checks"] if cc["claim_id"] != meta["canary_id"]]
    return clean(pulse)


def edit(pulse, strike=(), add=()):
    """Checkpoint edits: strike items by id, or add your own item as 'text | url'."""
    strike = {x.strip().upper() for x in strike}
    pulse["items"] = [it for it in pulse["items"] if it["id"] not in strike]
    for n, a in enumerate(add, 1):
        text, _, url = a.partition("|")
        pulse["items"].append({"id": f"U{n}", "kind": "trend", "headline": text.strip(), "why": "Added by the reviewer.",
                               "persona_ids": list(pulse["seat"]), "claim_ids": [], "drift": "none",
                               "url": url.strip() or None, "source": "reviewer", "date": today(), "window_days": 0,
                               "tier": 2, "origin": "reviewer"})
    pulse["approved"] = True
    return pulse


def brief_md(pulse, people):
    m = pulse["meta"]
    L = [f"# Market Pulse: {m['title']}", "", f"*{pulse['date']}. Review these items before the committee meets.*", ""]
    if pulse.get("banner"):
        L += [f"> **{pulse['banner']}**", ""]
    L += ["## The committee", ", ".join(people[x].display for x in pulse["seat"]), "",
          "## Claims under review"]
    L += [f"- **{c['id']}** {c['text']}" for c in m["claims"] if c["id"] != m["canary_id"]]
    L += ["", "## What changed in their world"]
    for it in pulse["items"]:
        who = ", ".join(people[x].name for x in it["persona_ids"] if x in people)
        when = it["date"] or f"last {it['window_days']} days"
        flag = " (forum sentiment)" if it["tier"] == 3 else ""
        L.append(f"- **{it['id']}** {it['headline']}{flag} *{it['why']}* For: {who}. "
                 f"[{it['source']}, {when}]({it['url']})")
    if pulse["competitor_changes"]:
        L += ["", "## Competitor pages today vs the Sept 28 library"]
        for c in pulse["competitor_changes"]:
            L.append(f"- **{c['company']}**: {c['change']}" + (f" Now reads: \"{c['new_line']}\"" if c.get("new_line") else ""))
    if pulse["claim_checks"]:
        L += ["", "## Claim checks"]
        L += [f"- **{c['claim_id']}** {c['status']}: {c['note']}" for c in pulse["claim_checks"]]
    L += ["", "---", "To continue: approve as is, strike items (for example M3), or add your own item."]
    return "\n".join(L)


SOURCE_FIELDS = ["url", "title", "source", "date", "tier", "group", "personas", "used_as", "query"]


def source_rows(pulse, people):
    """Every link the sweep touched: search results and competitor pages, with how each was used."""
    used = {it["url"]: it["id"] for it in pulse.get("items", []) if it.get("url")}
    rows = []
    for r in pulse.get("results", []):
        group = "competitor newsroom" if r.get("competitor") else ("market news" if len(r["for"]) > 1 and
                                                                  set(r["for"]) == set(pulse["seat"]) else "persona reading list")
        rows.append({"url": r["url"], "title": r["title"], "source": r["domain"], "date": r["date"] or "",
                     "tier": r["tier"], "group": group,
                     "personas": "; ".join(people[x].display for x in r["for"] if x in people),
                     "used_as": used.get(r["url"], ""), "query": r.get("query", "")})
    for pg in pulse.get("pages", []):
        rows.append({"url": pg["url"], "title": f"{pg['company']} live page", "source": pg["url"].split("/")[2],
                     "date": pulse["date"], "tier": 1, "group": "competitor page checked", "personas": "",
                     "used_as": f"{pg.get('kept', 0)} of {pg.get('total', 0)} library lines still live", "query": ""})
    return rows


def save_sources(run_dir, pulse, people, ledger_path):
    import csv
    rows = source_rows(pulse, people)
    with open(run_dir / "sources.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=SOURCE_FIELDS)
        w.writeheader()
        w.writerows(rows)
    # running ledger across runs: first seen, last seen, times seen, personas
    ledger = {}
    fields = ["url", "title", "source", "tier", "group", "first_seen", "last_seen", "times_seen", "personas", "runs"]
    if ledger_path.exists():
        with open(ledger_path, newline="", encoding="utf-8") as f:
            ledger = {r["url"]: r for r in csv.DictReader(f)}
    for r in rows:
        e = ledger.get(r["url"])
        if e:
            if run_dir.name in e["runs"].split("; "):
                continue
            e["last_seen"], e["times_seen"] = pulse["date"], str(int(e["times_seen"]) + 1)
            e["personas"] = "; ".join(sorted(set(filter(None, e["personas"].split("; ") + r["personas"].split("; ")))))
            e["runs"] = e["runs"] + "; " + run_dir.name
        else:
            ledger[r["url"]] = {"url": r["url"], "title": r["title"], "source": r["source"], "tier": r["tier"],
                                "group": r["group"], "first_seen": pulse["date"], "last_seen": pulse["date"],
                                "times_seen": "1", "personas": r["personas"], "runs": run_dir.name}
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    with open(ledger_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(ledger.values())


def save(run_dir, pulse, people):
    write_json(run_dir / "pulse.json", pulse)
    (run_dir / "pulse.md").write_text(brief_md(pulse, people), encoding="utf-8")
    save_sources(run_dir, pulse, people, run_dir.parent / "sources-ledger.csv")
