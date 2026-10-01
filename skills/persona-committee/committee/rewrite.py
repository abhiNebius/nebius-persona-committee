"""Stage 4: proposed messaging changes.

The Nebius marketing writer (nebius-marketing-writer: its house rules, the matching playbook and
its linter) rewrites the lines the committee flagged. Code then checks every rewrite (lint, copied
competitor phrasing, unsourced numbers) and the committee re-votes blind: users decide which version
wins, and any buyer who finds the new line not believable blocks it. At most two rounds.
"""
import random
import re
import subprocess
import tempfile
from pathlib import Path

from . import config as C
from .review import system_for
from .util import arr, i, obj, s, shingles, words

WRITE_SCHEMA = obj(rewrites=arr(obj(
    claim_id=s(),
    proposed=s("The new line, ready to publish except for [bracketed placeholders]"),
    why=s("One or two plain sentences on what changed and why, without 'I' (e.g. 'Replaced the superlative with...')"),
    answers=arr(s("Name of a committee member whose objection this answers")),
    pattern_quote_id=s("Q id of the competitor example whose structure this borrows, or null", nullable=True),
    support_ids=arr(s("N ids of the Nebius-published facts this line relies on")),
    pillar=s(enum=["build_faster", "scale_with_confidence", "own_your_intelligence", "none"]),
    evidence=arr(s("Where each fact comes from, e.g. 'Company Messaging Framework 2.0, Page 8'")),
    placeholders=arr(s("Each [bracketed] item a human must fill with a sourced fact")),
    also_proof=arr(s("Other published proof that fits this line but was left out to keep one proof per line")),
)))

VOTE_SCHEMA = obj(votes=arr(obj(
    claim_id=s(),
    prefer=s(enum=["A", "B", "same"]),
    a_score=i(lo=1, hi=7), b_score=i(lo=1, hi=7),
    a_believable=s(enum=["yes", "no"]), b_believable=s(enum=["yes", "no"]),
    why=s("One sentence, in your voice"),
)))


def _writer_rules(cfg, asset_type, lib):
    root = C.path(cfg, "writer_skill")
    house = (root / "references" / "house-rules.md")
    skill = (root / "SKILL.md")
    rules = house.read_text() if house.exists() else ""
    nn = ""
    if skill.exists():
        m = re.search(r"## Non-negotiables.*?(?=\n## |\Z)", skill.read_text(), re.S)
        nn = m.group(0) if m else ""
    pb_name, pb = lib.playbook(asset_type)
    sources = []
    for p in cfg["paths"]["claims_sources"]:
        f = Path(p).expanduser()
        if f.exists():
            sources.append(f"### SOURCE: {f.stem}\n{f.read_text()}")
    return rules, nn, pb_name, pb, "\n\n".join(sources)


def _lint(cfg, text, asset_type):
    script = C.path(cfg, "writer_skill") / "scripts" / "lint_asset.py"
    if not script.exists():
        return {"ran": False, "errors": [], "warnings": []}
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as f:
        f.write(text + "\n")
        tmp = f.name
    p = subprocess.run(["python3", str(script), tmp, "--type", str(asset_type)], capture_output=True, text=True)
    Path(tmp).unlink(missing_ok=True)
    errs = [ln.strip()[5:].strip() for ln in p.stdout.splitlines() if ln.strip().startswith("ERROR") and re.search(r"L\d+:", ln)]
    warns = [ln.strip()[4:].strip() for ln in p.stdout.splitlines() if ln.strip().startswith("WARN") and re.search(r"L\d+:", ln)]
    return {"ran": True, "errors": errs, "warnings": warns}


LIMITS = {  # (web page, one-pager or document), in words; see references/rewrite-rules.md
    "headline": (8, 10), "subhead": (16, 18), "pillar": (25, 30), "proof": (14, 18), "cta": (5, 5), "body": (25, 30)}


def _metrics(text):
    """Distinct figures in a line, ignoring years, versions after a rating name and anything in brackets."""
    bare = re.sub(r"\[[^\]]*\]", " ", text)
    bare = re.sub(r"\b(ClusterMAX|MLPerf|Inference|v)\s*\d+(\.\d+)*", " ", bare, flags=re.I)
    figs = re.findall(r"(?<![A-Za-z\d.,])\d[\d,.]*", bare)  # skip model and product names such as R1, H100, GB300
    return [n.rstrip(".,") for n in figs if not re.fullmatch(r"(19|20)\d\d", n.rstrip(".,"))]


def _numbers(text):
    bare = re.sub(r"\[[^\]]*\]", " ", text)
    return set(re.findall(r"\d+(?:[.,]\d+)?", bare))


def check(cfg, lib, rw, original, sources_text, asset_type, part="body", medium="web"):
    issues = []
    lim = LIMITS.get(part, LIMITS["body"])[0 if medium == "web" else 1]
    n_words = len(rw["proposed"].split())
    if n_words > lim:
        issues.append(f"Too long for a {part}: {n_words} words (limit {lim})")
    sentences = [x for x in re.split(r"(?<=[.!?])\s+", rw["proposed"].strip()) if x]
    if len(sentences) > 2:
        issues.append(f"{len(sentences)} sentences (limit 2)")
    if len(_metrics(rw["proposed"])) > 3:  # a figure, its unit count and a baseline is still one proof
        issues.append("Stacks several figures; keep one proof per line and move the rest to also_proof")
    comp = set().union(*(shingles(ln) for _, ln in lib.corpus())) if lib.entries else set()
    shared = shingles(rw["proposed"]) & comp
    if shared:
        issues.append("Shares wording with competitor copy: \"" + sorted(shared)[0] + "\"")
    allowed = _numbers(original) | _numbers(sources_text)
    bad = sorted(n for n in _numbers(rw["proposed"]) if n not in allowed)
    if bad:
        issues.append("Numbers not found in the claims sources or the original: " + ", ".join(bad))
    ph = re.findall(r"\[[^\]]*\]", rw["proposed"])
    if len(ph) > 1:
        issues.append(f"Too many placeholders to read as copy ({len(ph)}; the limit is 1)")
    lint = _lint(cfg, rw["proposed"], asset_type)
    issues += ["Lint: " + e for e in lint["errors"]]
    return issues, lint


def write(engine, cfg, lib, people, pulse, reviews, judge_out, pool, feedback=None):
    meta = pulse["meta"]
    rules, nn, pb_name, pb, sources = _writer_rules(cfg, meta["asset_type"], lib)
    claim = {c["id"]: c["text"] for c in meta["claims"]}
    pillar_of = {c["id"]: c.get("pillar", "none") for c in meta["claims"]}
    part_of = {c["id"]: c.get("part", "body") for c in meta["claims"]}
    medium = "web" if str(pulse.get("source", "")).startswith("http") else "document"
    facts = pulse.get("nebius", {})
    npool = facts.get("pool", {})
    unused_txt = "\n".join(f"{x['passage_id']} ({npool.get(x['passage_id'], {}).get('date') or 'recent'}): {x['quote']}"
                            for x in facts.get("unused", []) + facts.get("standing", []))
    rows = []
    for t in judge_out["rewrite_targets"]:
        objs = []
        for pid, rv in reviews.items():
            hit = next((x for x in rv["claims"] if x["claim_id"] == t["claim_id"]), None)
            if hit and hit["verdict"] != "lands":
                objs.append(f"{people[pid].display}: {hit['why']}")
        fb = (feedback or {}).get(t["claim_id"])
        sup = [x for x in facts.get("supports", []) if x["claim_id"] == t["claim_id"]]
        sup_txt = "\n".join(f"  {x['passage_id']} ({npool.get(x['passage_id'], {}).get('date') or 'recent'}): {x['quote']}" for x in sup)
        pt = part_of.get(t["claim_id"], "body")
        lim = LIMITS.get(pt, LIMITS["body"])[0 if medium == "web" else 1]
        rows.append(f"{t['claim_id']} [{pt}, max {lim} words; pillar {pillar_of.get(t['claim_id'], 'none')}]: \"{claim.get(t['claim_id'], '')}\"\nPROBLEM: {t['problem']}\n"
                    f"THE COMMITTEE ASKED FOR: {t['asks']}\n"
                    f"OBJECTIONS:\n- " + "\n- ".join(objs[:6]) + (f"\nNEBIUS FACTS FOR THIS LINE:\n{sup_txt}" if sup_txt else "")
                    + (f"\nLAST ROUND FEEDBACK: {fb}" if fb else ""))
    pats = "\n".join(f"{p['quote_id']} ({pool[p['quote_id']]['company']}): \"{pool[p['quote_id']]['quote']}\" "
                     f"PATTERN: {p['title']}. {p['explanation']}" for p in judge_out["patterns"] if p["quote_id"] in pool)
    system = ("You are the Nebius marketing writer. Follow the REWRITE RULES first, then the house rules, the playbook and "
              "the non-negotiables. Usable beats complete: one claim, one proof, within the word limit for the element "
              f"type on a {medium}. "
              "Rewrite each flagged line so it answers the committee's objections AND makes its Nebius value pillar shine "
              "(Build faster, Scale with confidence, Own your intelligence). This is messaging, not a spec sheet: lead with what "
              "the buyer gets, then the proof. Pull supporting points from the Nebius-published facts given (cite them in "
              "support_ids). Keep each line close to the original length. "
              "Use only facts found in the claims sources, the house rules, the non-negotiables or the original line; use them "
              "wherever they fit (for example a rating the house rules name). Any fact you still need becomes a "
              "[bracketed placeholder], but a line may carry at most 3 placeholders and must read as finished copy a buyer "
              "would see on the page, not a template. Prefer a shorter, fully sourced line over a longer bracketed one. "
              "Competitor examples show structure only: never reuse their wording. "
              "No em-dashes.\n\n# REWRITE RULES\n" + C.reference("rewrite-rules.md") + "\n\n# HOUSE RULES\n" + rules + "\n\n# NON-NEGOTIABLES\n" + nn +
              f"\n\n# PLAYBOOK ({pb_name})\n" + pb + "\n\n# CLAIMS SOURCES (the only allowed facts)\n" + sources)
    prompt = f"ASSET: {meta['title']} (asset type {meta['asset_type']})\n\nLINES TO REWRITE\n" + "\n\n".join(rows) + \
             f"\n\nPATTERNS WORTH BORROWING (structure only)\n{pats or 'none'}" + \
             f"\n\nOTHER NEBIUS-PUBLISHED PROOF YOU MAY USE\n{unused_txt or 'none'}"
    out = engine.run(system, prompt, WRITE_SCHEMA, tier="deep", label="rewrite:writer")
    fact_text = "\n".join(p.get("text", "") for p in npool.values())
    for rw in out["rewrites"]:
        rw["original"] = claim.get(rw["claim_id"], "")
        rw["support_ids"] = [x for x in rw.get("support_ids", []) if x in npool]
        rw["issues"], rw["lint"] = check(cfg, lib, rw, rw["original"], sources + "\n" + rules + "\n" + nn + "\n" + fact_text,
                                         meta["asset_type"], part_of.get(rw["claim_id"], "body"), medium)
        rw["words"] = len(rw["proposed"].split())
        if rw["pattern_quote_id"] not in pool:
            rw["pattern_quote_id"] = None
    return [rw for rw in out["rewrites"] if rw["claim_id"] in claim]


def vote(engine, people, pulse, reviews, rewrites):
    """Blind A/B re-vote by the seated committee on each rewrite."""
    order = {}
    lines = []
    for rw in rewrites:
        flip = random.random() < 0.5
        order[rw["claim_id"]] = flip
        a, b_ = (rw["proposed"], rw["original"]) if flip else (rw["original"], rw["proposed"])
        lines.append(f"{rw['claim_id']}\n  A: {a}\n  B: {b_}")
    prompt = ("Two versions of each line follow, in random order. For each, say which you prefer, score both 1 to 7 "
              "overall, and say whether each is believable to you. Judge each line as it would read on the page today. "
              "A [bracketed] item is a fact nobody has supplied yet: do not assume it will be good, and mark a line down "
              "if it reads like a template rather than finished copy.\n\n" + "\n\n".join(lines))
    jobs = [(pid, dict(system=system_for(people[pid]), prompt=prompt, schema=VOTE_SCHEMA, tier="fast",
                       label=f"vote:{pid}")) for pid in reviews]
    res = engine.map(jobs)
    tally = {rw["claim_id"]: {"users": {"new": 0, "old": 0, "same": 0}, "vetoes": [], "old_scores": [], "new_scores": [],
                              "whys": []} for rw in rewrites}
    for pid, r in res.items():
        if isinstance(r, Exception):
            continue
        g = people[pid].group
        for v in r["votes"]:
            if v["claim_id"] not in tally:
                continue
            flip = order[v["claim_id"]]
            new_s, old_s = (v["a_score"], v["b_score"]) if flip else (v["b_score"], v["a_score"])
            new_ok = v["a_believable"] if flip else v["b_believable"]
            pref = "same" if v["prefer"] == "same" else ("new" if (v["prefer"] == "A") == flip else "old")
            t = tally[v["claim_id"]]
            t["new_scores"].append(new_s)
            t["old_scores"].append(old_s)
            t["whys"].append(f"{people[pid].name}: {v['why']}")
            if g == "users":
                t["users"][pref] += 1
            if g == "buyers" and new_ok == "no":
                t["vetoes"].append(pid)
    for rw in rewrites:
        t = tally[rw["claim_id"]]
        avg = lambda xs: round(sum(xs) / len(xs), 1) if xs else None
        t["before"], t["after"] = avg(t["old_scores"]), avg(t["new_scores"])
        users_win = t["users"]["new"] > t["users"]["old"] or (not any(t["users"].values()) and (t["after"] or 0) > (t["before"] or 0))
        if rw["issues"]:
            t["status"] = "failed_checks"
        elif t["vetoes"]:
            t["status"] = "blocked_by_buyer"
        elif users_win:
            t["status"] = "recommended"
        else:
            t["status"] = "users_prefer_original"
        rw["vote"] = t
    return rewrites


def run(engine, cfg, lib, people, pulse, reviews, judge_out, pool):
    if not judge_out["rewrite_targets"]:
        return []
    rounds = cfg["committee"]["rewrite_rounds"]
    final, feedback = {}, None
    for rnd in range(1, rounds + 1):
        rws = vote(engine, people, pulse, reviews, write(engine, cfg, lib, people, pulse, reviews, judge_out, pool, feedback))
        for rw in rws:
            rw["round"] = rnd
            prev = final.get(rw["claim_id"])
            if not prev or prev["vote"]["status"] != "recommended":
                final[rw["claim_id"]] = rw
        pending = [cid for cid, rw in final.items() if rw["vote"]["status"] != "recommended"]
        if not pending or rnd == rounds:
            break
        feedback = {cid: "; ".join(final[cid]["issues"] + final[cid]["vote"]["whys"][:4]) for cid in pending}
        judge_out = dict(judge_out, rewrite_targets=[t for t in judge_out["rewrite_targets"] if t["claim_id"] in pending])
    return list(final.values())
