"""Stage 3: the judge.

Code computes every number (scores, ranking, vetoes, canary, blind result, score changes).
A model then writes the verdict in plain English. It can cite competitor copy only by Q id from a
pool of real excerpts, so every quote in the report is verbatim by construction.
"""
from collections import Counter

from . import config as C
from .review import CRITERIA, LABELS, mean_score
from .util import arr, obj, s


def compute(people, pulse, reviews, vendors, debate):
    pc = {}
    for pid, rv in reviews.items():
        pc[pid] = {"mean": mean_score(rv), **{k: rv["scores"][k]["score"] for k in CRITERIA}}
    groups = {}
    for g in ("users", "buyers"):
        ids = [x for x in reviews if people[x].group == g]
        groups[g] = {"ids": ids, **{k: round(sum(pc[x][k] for x in ids) / len(ids), 1) if ids else None
                                    for k in CRITERIA + ["mean"]}}
    ranking = sorted(groups["users"]["ids"], key=lambda x: -pc[x]["mean"]) + \
              sorted(groups["buyers"]["ids"], key=lambda x: -pc[x]["mean"])

    meta, canary = pulse["meta"], pulse["meta"]["canary_id"]
    claims = []
    for c in meta["claims"]:
        v = {"users": Counter(), "buyers": Counter()}
        vetoes = []
        for pid, rv in reviews.items():
            hit = next((x for x in rv["claims"] if x["claim_id"] == c["id"]), None)
            if not hit:
                continue
            v[people[pid].group][hit["verdict"]] += 1
            if people[pid].group == "buyers" and hit["verdict"] == "fails" and \
                    (rv["scores"]["credible"]["score"] <= 3 or rv["meeting"] == "no"):
                vetoes.append(pid)
        allv = v["users"] + v["buyers"]
        n = sum(allv.values()) or 1
        verdict = "fails" if allv["fails"] / n >= 0.5 else "lands" if allv["lands"] / n >= 0.5 else "mixed"
        claims.append({"id": c["id"], "text": c["text"], "canary": c["id"] == canary,
                       "users": dict(v["users"]), "buyers": dict(v["buyers"]), "verdict": verdict, "vetoes": vetoes})
    can = next(c for c in claims if c["canary"])
    can_n = sum(can["users"].values()) + sum(can["buyers"].values())
    can_bad = can["users"].get("weak", 0) + can["users"].get("fails", 0) + can["buyers"].get("weak", 0) + can["buyers"].get("fails", 0)
    canary_pass = can_n > 0 and can_bad / can_n > 0.5

    labels = {v["label"]: v["company"] for v in vendors}
    ours = next(v["label"] for v in vendors if v["company"] == "Nebius")
    ranks, picks, cant_tell = [], Counter(), 0
    for rv in reviews.values():
        bl = rv["blind"]
        if ours in bl["ranking"]:
            ranks.append(bl["ranking"].index(ours) + 1)
        picks[labels.get(bl["meeting_pick"], "none")] += 1
        cant_tell += 0 if bl["could_tell_apart"] else 1
    blind = {"our_label": ours, "labels": labels, "vendors": len(vendors),
             "avg_rank": round(sum(ranks) / len(ranks), 1) if ranks else None,
             "first_place": sum(1 for r in ranks if r == 1), "meeting_picks": dict(picks),
             "could_not_tell_apart": cant_tell, "n": len(reviews)}
    stands = {}
    for rv in reviews.values():
        for x in rv["blind"]["vendors"]:
            stands.setdefault(labels.get(x["label"], x["label"]), []).append(x["stands_out"])
    blind["stands_out"] = {k: round(sum(v) / len(v), 1) for k, v in stands.items() if v}

    moves = []
    for pt in debate:
        for t in pt.get("turns", []):
            sc = t.get("score_change") or {}
            if sc.get("changed") == "yes" and sc.get("from") is not None and sc["from"] != sc["new_score"]:
                moves.append({"persona": t["persona"], "criterion": sc["criterion"], "from": sc["from"],
                              "to": sc["new_score"], "why": sc["why"]})
    return {"per_persona": pc, "groups": groups, "ranking": ranking, "claims": claims,
            "canary": {"id": canary, "pass": canary_pass, "flagged_weak": can_bad, "n": can_n},
            "blind": blind, "moves": moves}


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
                pool[f"Q{n}"] = {"company": comp, "quote": ln, "url": e.url, "date": e.date, "title": e.title,
                                 "origin": "library"}
                taken += 1
    for c in pulse.get("competitor_changes", []):
        if c.get("new_line"):
            n += 1
            pool[f"Q{n}"] = {"company": c["company"], "quote": c["new_line"], "url": c["url"],
                             "date": pulse["date"], "title": "live page", "origin": "live"}
    return pool


JUDGE_SCHEMA = obj(
    headline=s("The verdict in one sentence, like a newspaper headline written as a full sentence"),
    dek=s("Two short sentences that explain the verdict"),
    what_changed=arr(obj(pulse_id=s(), line=s("One sentence: how this live item shaped the verdict"))),
    persona_lines=arr(obj(persona=s(), line=s("Their verdict in one plain sentence, third person, naming them"))),
    claim_lines=arr(obj(claim_id=s(), line=s("One plain sentence on how the committee read this claim"))),
    blind_story=s("Two or three sentences telling the blind test result plainly, using the numbers given"),
    overlap=arr(obj(claim_id=s(), status=s(enum=["table_stakes", "contested", "open_lane"]),
                    explanation=s("One or two plain sentences"), quote_ids=arr(s("Q id")))),
    patterns=arr(obj(title=s("A short plain title, e.g. 'Lead with the referee'"),
                     explanation=s("Two sentences: what they do and why it would work on which of our personas"),
                     quote_id=s("Q id of the literal example"))),
    issues=arr(obj(kind=s(enum=["copy", "product"]), line=s(), owner=s("Who should own it"))),
    rewrite_targets=arr(obj(claim_id=s(), problem=s("Plain sentence"), asks=s("What the committee asked for instead"))),
)


def write(engine, cfg, people, pulse, reviews, debate, numbers, pool):
    meta = pulse["meta"]
    name = {pid: people[pid].display for pid in reviews}
    rv_txt = "\n".join(
        f"{name[pid]} ({people[pid].group}, mean {numbers['per_persona'][pid]['mean']}): {rv['first_reaction']} "
        f"Stop: {rv['stopping_objection']['text']} Recommends: {rv['key_recommendation']}" for pid, rv in reviews.items())
    claims_txt = "\n".join(f"{c['id']} [{c['verdict']}] users {c['users']} buyers {c['buyers']} vetoes {c['vetoes']}: {c['text']}"
                           for c in numbers["claims"] if not c["canary"])
    deb = "\n".join(f"{name.get(t['persona'])}: {t['text']}" for pt in debate for t in pt.get("turns", []))
    items = "\n".join(f"{it['id']}: {it['headline']}" for it in pulse.get("items", []))
    q = "\n".join(f"{k} {v['company']}: \"{v['quote']}\"" for k, v in pool.items())
    b = numbers["blind"]
    blind_txt = (f"Nebius was {b['our_label']}. Average rank {b['avg_rank']} of {b['vendors']}. First place {b['first_place']} of {b['n']}. "
                 f"Meeting picks by company: {b['meeting_picks']}. Could not tell vendors apart: {b['could_not_tell_apart']} of {b['n']}. "
                 f"Stands out (avg 1-7): {b['stands_out']}. Vendors: {b['labels']}.")
    system = ("You are the editor of a buying committee report for Nebius marketing. Write like a top journalist: "
              "the point first, short sentences, concrete, plain words, no jargon. Use the criteria names "
              + ", ".join(LABELS.values()) + ". Report what the committee said; do not add your own opinions or facts. "
              "Cite competitor copy only by Q id in the quote_ids and quote_id fields; never write a competitor quote yourself, "
              "and never mention Q or R ids in any prose field. "
              "Mark a claim table_stakes if two or more competitors in the pool say the same thing, contested if one does, "
              "open_lane if none does. Pick 2 to 4 patterns worth borrowing, each with the Q id of a literal example. "
              "Pick at most 5 rewrite targets, weakest and most vetoed first. Separate copy problems from product problems. "
              "No em-dashes.\n\nSTYLE GUIDE\n" + C.reference("report-style.md"))
    prompt = (f"ASSET: {meta['title']}: {meta['summary']}\n\nCLAIMS (with committee verdicts)\n{claims_txt}\n\n"
              f"PRIVATE REVIEWS\n{rv_txt}\n\nDEBATE\n{deb or 'none'}\n\nBLIND TEST\n{blind_txt}\n\n"
              f"LIVE ITEMS\n{items or 'none'}\n\nQUOTE POOL\n{q or 'none'}")
    out = engine.run(system, prompt, JUDGE_SCHEMA, tier="deep", label="judge")
    out["overlap"] = [dict(o, quote_ids=[x for x in o["quote_ids"] if x in pool]) for o in out["overlap"]]
    out["patterns"] = [p for p in out["patterns"] if p["quote_id"] in pool]
    out["rewrite_targets"] = [t for t in out["rewrite_targets"] if t["claim_id"] != meta["canary_id"]][:cfg["committee"]["max_rewrite_lines"]]
    return out
