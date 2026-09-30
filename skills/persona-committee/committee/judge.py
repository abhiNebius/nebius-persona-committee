"""Stage 3: the judge.

Code computes every number: the message-by-persona grid, message ranking, vetoes, canary, blind
result, persona averages and score changes. A model then writes the verdict like a marketing leader
reviewing a draft, under hard word limits. It can cite competitor copy only by Q id and Nebius facts
only by N id, so every quote in the report is verbatim by construction.
"""
from collections import Counter

from . import config as C
from . import nebius as NB
from .review import CRITERIA, LABELS, mean_score
from .util import arr, obj, s

LIMITS = {"verdict": 14, "works": 20, "fails": 20, "fix": 20}
PILLARS = {"build_faster": "Build faster", "scale_with_confidence": "Scale with confidence",
           "own_your_intelligence": "Own your intelligence"}


def _avg(xs):
    return round(sum(xs) / len(xs), 1) if xs else None


def compute(people, pulse, reviews, vendors, debate):
    users = [x for x in pulse["seat"] if x in reviews and people[x].group == "users"]
    buyers = [x for x in pulse["seat"] if x in reviews and people[x].group == "buyers"]
    meta, canary = pulse["meta"], pulse["meta"]["canary_id"]

    grid = []
    for c in meta["claims"]:
        row = {"id": c["id"], "text": c["text"], "label": c.get("label", ""), "part": c.get("part", ""),
               "pillar": c.get("pillar", "none"), "canary": c["id"] == canary, "scores": {}, "verdicts": {}, "vetoes": []}
        for pid in users + buyers:
            hit = next((x for x in reviews[pid]["claims"] if x["claim_id"] == c["id"]), None)
            if not hit:
                continue
            row["scores"][pid] = hit["score"]
            row["verdicts"][pid] = hit["verdict"]
            if pid in buyers and hit["verdict"] == "fails" and hit["score"] <= 2:
                row["vetoes"].append(pid)
        row["users"] = _avg([row["scores"][x] for x in users if x in row["scores"]])
        row["buyers"] = _avg([row["scores"][x] for x in buyers if x in row["scores"]])
        row["all"] = _avg(list(row["scores"].values()))
        v = Counter(row["verdicts"].values())
        n = sum(v.values()) or 1
        row["verdict"] = "fails" if v["fails"] / n >= 0.5 else "lands" if v["lands"] / n >= 0.5 else "mixed"
        grid.append(row)
    real = [r for r in grid if not r["canary"]]
    # users vote first: rank by the users' average, then the buyers'
    ranked = sorted(real, key=lambda r: (-(r["users"] or 0), -(r["buyers"] or 0)))
    for n, r in enumerate(ranked, 1):
        r["rank"] = n

    can = next(r for r in grid if r["canary"])
    can_bad = sum(1 for v in can["verdicts"].values() if v != "lands")
    canary_pass = bool(can["verdicts"]) and can_bad / len(can["verdicts"]) > 0.5

    pillars = {}
    for key in PILLARS:
        rows = [r for r in real if r["pillar"] == key]
        pillars[key] = {"messages": [r["id"] for r in rows], "avg": _avg([r["all"] for r in rows if r["all"]])}

    per = {pid: {"mean": mean_score(rv), **{k: rv["scores"][k]["score"] for k in CRITERIA}} for pid, rv in reviews.items()}

    labels = {v["label"]: v["company"] for v in vendors}
    ours = next(v["label"] for v in vendors if v["company"] == "Nebius")
    ranks, picks, cant_tell, stands = [], Counter(), 0, {}
    for rv in reviews.values():
        bl = rv["blind"]
        if ours in bl["ranking"]:
            ranks.append(bl["ranking"].index(ours) + 1)
        picks[labels.get(bl["meeting_pick"], "none")] += 1
        cant_tell += 0 if bl["could_tell_apart"] else 1
        for x in bl["vendors"]:
            stands.setdefault(labels.get(x["label"], x["label"]), []).append(x["stands_out"])
    blind = {"our_label": ours, "labels": labels, "vendors": len(vendors), "avg_rank": _avg(ranks),
             "first_place": sum(1 for r in ranks if r == 1), "meeting_picks": dict(picks),
             "could_not_tell_apart": cant_tell, "n": len(reviews),
             "stands_out": {k: _avg(v) for k, v in stands.items()}}

    moves = []
    for th in debate:
        for t in th.get("turns", []):
            sc = t.get("score_change") or {}
            if sc.get("changed") == "yes" and sc.get("from") is not None and sc["from"] != sc["new_score"]:
                moves.append({"persona": t["persona"], "criterion": sc["criterion"], "from": sc["from"],
                              "to": sc["new_score"], "why": sc["why"]})
    return {"users": users, "buyers": buyers, "grid": grid, "ranked": [r["id"] for r in ranked],
            "canary": {"id": canary, "pass": canary_pass, "flagged_weak": can_bad, "n": len(can["verdicts"])},
            "pillars": pillars, "per_persona": per, "blind": blind, "moves": moves,
            "ranking": sorted(users, key=lambda x: -per[x]["mean"]) + sorted(buyers, key=lambda x: -per[x]["mean"])}


def quote_pool(cfg, lib, pulse, per_company=10):
    """Real competitor lines the judge may cite, by Q id."""
    pool, n = {}, 0
    at = pulse["meta"]["asset_type"]
    for comp in pulse.get("competitors") or []:
        es = sorted(lib.for_company(comp), key=lambda e: (at not in e.asset_types, "01" not in e.asset_types))
        taken = 0
        for e in es:
            for ln in e.lines:
                if taken >= per_company or len(ln) < 25 or ln.startswith("|"):
                    continue
                n += 1
                pool[f"Q{n}"] = {"company": comp, "quote": ln, "url": e.url, "date": e.date, "title": e.title, "origin": "library"}
                taken += 1
    for c in pulse.get("competitor_changes", []):
        if c.get("new_line"):
            n += 1
            pool[f"Q{n}"] = {"company": c["company"], "quote": c["new_line"], "url": c["url"], "date": pulse["date"],
                             "title": "live page", "origin": "live"}
    return pool


JUDGE_SCHEMA = obj(
    verdict=s("The verdict in 14 words or fewer. Sharp, plain, bright, like a CMO's one-line read of a draft"),
    works=s("What works, 20 words or fewer"),
    fails=s("What fails, 20 words or fewer"),
    fix=s("The one fix that matters most, 20 words or fewer"),
    message_notes=arr(obj(claim_id=s(), note=s("A crisp critique of this message, 18 words or fewer"))),
    pillars=arr(obj(pillar=s(enum=list(PILLARS)), status=s(enum=["lands", "weak", "missing"]),
                    line=s("One sentence, 20 words or fewer, on how the asset carries this value pillar"))),
    corrections=arr(obj(who=s("Persona name, or 'the market check'"), assumed=s("What they assumed, plainly"),
                        actually=s("What Nebius has actually published, plainly"), passage_id=s("N id"))),
    unused_proof=arr(obj(passage_id=s("N id"), line=s("One sentence: the proof and where it belongs on the asset"))),
    blind_story=s("Two sentences telling the blind test result plainly, using the numbers given"),
    overlap=arr(obj(claim_id=s(), status=s(enum=["table_stakes", "contested", "open_lane"]),
                    explanation=s("One plain sentence"), quote_ids=arr(s("Q id")))),
    patterns=arr(obj(title=s("A short plain title"), explanation=s("Two sentences: what they do and why it works for which persona"),
                     quote_id=s("Q id"))),
    issues=arr(obj(kind=s(enum=["copy", "product"]), line=s(), owner=s())),
    rewrite_targets=arr(obj(claim_id=s(), problem=s("Plain sentence"), asks=s("What the committee asked for instead"))),
)


def write(engine, cfg, people, pulse, reviews, debate, numbers, pool):
    meta = pulse["meta"]
    name = {pid: people[pid].display for pid in reviews}
    grid = "\n".join(
        f"{r['id']} [{r['label']}; {r['part']}; pillar {r['pillar']}] users {r['users']} buyers {r['buyers']} "
        f"verdict {r['verdict']} vetoes {[people[x].name for x in r['vetoes']]}: {r['text']}"
        for r in numbers["grid"] if not r["canary"])
    why = "\n".join(f"{name[pid]} on {c['claim_id']} ({c['score']}): {c['why']}" for pid, rv in reviews.items() for c in rv["claims"]
                    if c["claim_id"] != meta["canary_id"])
    stops = "\n".join(f"{name[pid]}: stop = {rv['stopping_objection']['text']}; recommends = {rv['key_recommendation']}"
                      for pid, rv in reviews.items())
    deb = "\n".join(f"{name.get(t['persona'])}: {t['text']}" for th in debate for t in th.get("turns", []))
    items = "\n".join(f"{it['id']}: {it['headline']}" for it in pulse.get("items", []))
    q = "\n".join(f"{k} {v['company']}: \"{v['quote']}\"" for k, v in pool.items())
    b = numbers["blind"]
    blind_txt = (f"Nebius was {b['our_label']}. Average rank {b['avg_rank']} of {b['vendors']}. First place {b['first_place']} of {b['n']}. "
                 f"Meeting picks: {b['meeting_picks']}. Could not tell apart: {b['could_not_tell_apart']} of {b['n']}. "
                 f"Stands out (avg 1-7): {b['stands_out']}.")
    system = ("You are a senior marketing leader writing the verdict on a draft for your team. Clear, simple and bright. "
              "The point first. Short sentences. No jargon, no hedging stacks. Respect every word limit. You grade the messaging: "
              "does the asset make Nebius's value pillars shine (Build faster, Scale with confidence, Own your intelligence), "
              "not only whether the claims are technically true. Report what the committee said; add no facts of your own. "
              "VERIFIED NEBIUS FACTS are what Nebius has published: never contradict them, and list in corrections every place "
              "a persona, the thread or the market check assumed something they directly contradict (for example, assuming Nebius "
              "lacks a rating it has). A difference in precision is not a contradiction: 'more than a million' is consistent "
              "with 1.2 million. Pick up to three unused_proof items from those facts that the asset leaves out. Cite competitor "
              "copy only by Q id and Nebius facts only by N id, in the id fields; never mention ids in prose. Mark a message "
              "table_stakes if two or more competitors say the same thing, contested if one does, open_lane if none. Rewrite "
              "targets: at most 5, headline and pillar lines first, then the weakest and most vetoed. No em-dashes.\n\n"
              "STYLE GUIDE\n" + C.reference("report-style.md"))
    prompt = (f"ASSET: {meta['title']}: {meta['summary']}\n\nMESSAGE GRID (ranked by users first)\n{grid}\n\n"
              f"WHAT EACH PERSONA SAID PER MESSAGE\n{why}\n\nSTOPPERS\n{stops}\n\nTHE THREAD\n{deb or 'none'}\n\n"
              f"BLIND TEST\n{blind_txt}\n\nLIVE ITEMS\n{items or 'none'}\n\n"
              f"VERIFIED NEBIUS FACTS\n{NB.brief(pulse.get('nebius', {}))}\n\nCOMPETITOR QUOTE POOL\n{q or 'none'}")
    out = engine.run(system, prompt, JUDGE_SCHEMA, tier="deep", label="judge")
    out = tighten(engine, out)
    npool = pulse.get("nebius", {}).get("pool", {})
    out["overlap"] = [dict(o, quote_ids=[x for x in o["quote_ids"] if x in pool]) for o in out["overlap"]]
    out["patterns"] = [p for p in out["patterns"] if p["quote_id"] in pool]
    out["corrections"] = [c for c in out["corrections"] if c["passage_id"] in npool]
    out["unused_proof"] = [u for u in out["unused_proof"] if u["passage_id"] in npool][:3]
    out["rewrite_targets"] = [t for t in out["rewrite_targets"] if t["claim_id"] != meta["canary_id"]][:cfg["committee"]["max_rewrite_lines"]]
    return out


def tighten(engine, out):
    """Enforce word limits on the page-one lines. One small call rewrites only what is over."""
    over = {k: out[k] for k, n in LIMITS.items() if len(out.get(k, "").split()) > n}
    notes = [n for n in out.get("message_notes", []) if len(n["note"].split()) > 18]
    if not over and not notes:
        return out
    fields = {**{k: s(f"{LIMITS[k]} words or fewer") for k in over}, "notes": arr(obj(claim_id=s(), note=s("18 words or fewer")))}
    prompt = ("Shorten each item to its word limit. Keep the meaning and the sharpness. Plain words. No em-dashes.\n\n"
              + "\n".join(f"{k} (max {LIMITS[k]}): {v}" for k, v in over.items())
              + "\n\nNOTES (max 18 each):\n" + "\n".join(f"{n['claim_id']}: {n['note']}" for n in notes))
    try:
        t = engine.run("You are a tight copy editor.", prompt, obj(**fields), tier="fast", label="judge:tighten")
    except Exception:
        return out
    for k in over:
        out[k] = t.get(k) or out[k]
    fixed = {n["claim_id"]: n["note"] for n in t.get("notes", [])}
    for n in out["message_notes"]:
        n["note"] = fixed.get(n["claim_id"], n["note"])
    return out
