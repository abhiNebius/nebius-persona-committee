"""Stage 1: private reviews. One isolated call per seated persona, run in parallel.

Each persona gets its fixed identity (the persona file), what changed in its world this month
(its Market Pulse items), the copy, the numbered claims (with a hidden canary), and a blind
side-by-side against competitor copy labeled Vendor A, B, C.
"""
import random
import re

from . import config as C
from .util import arr, b, i, obj, s

CRITERIA = ["jtbd", "credible", "emotional", "different", "clear"]
LABELS = {"jtbd": "Fits their job", "credible": "Believable", "emotional": "Meets the feeling",
          "different": "Stands out", "clear": "Clear"}

SESSION_RULES = """
BUYING COMMITTEE REVIEW: RULES FOR THIS SESSION
- Stay in character: first person, your vocabulary, your skepticism, your priorities.
- You do not know who asked for this review. Judge the copy on its merits.
- "This week in your world" lists real items from sources you read. You may mention them naturally
  ("I saw on SemiAnalysis last week...") and must list their IDs in pulse_used. Never invent news, numbers or quotes.
- Score each criterion 1 to 7 using the anchors below. Every score needs a one-sentence reason in your voice.
- Score every numbered message 1 to 7 (7: this would make you forward the page; 4: neutral; 1: you would stop reading),
  and mark it lands, weak or fails. Judge the message as marketing: does it make the offer compelling to you, not only
  is it technically true.
- In the blind comparison you see three vendors with names removed. Rank them honestly.
- Keep every text field short: one to three sentences. Plain words. No em-dashes.
"""


def _schema(labels):
    crit = obj(score=i(lo=1, hi=7), why=s("One sentence, in your voice"))
    return obj(
        first_reaction=s("Two or three sentences, in your voice"),
        scores=obj(**{k: crit for k in CRITERIA}),
        claims=arr(obj(claim_id=s(), score=i("1 to 7: how much this message moves you", lo=1, hi=7),
                       verdict=s(enum=["lands", "weak", "fails"]), why=s("One short sentence in your voice, 20 words at most"))),
        stopping_objection=obj(text=s("The one thing that would stop you"),
                               stage=s("When it bites: first look, evaluation, POC, security review, contract, renewal")),
        missing=arr(s()),
        words_that_lost_me=arr(s("Exact words from the copy")),
        meeting=s(enum=["yes", "no", "maybe"]),
        meeting_why=s(),
        one_rewrite=s("The single line you would want instead"),
        key_recommendation=s("The one change you would tell the marketing team to make, in one sentence"),
        pulse_used=arr(s()),
        blind=obj(
            ranking=arr(s(enum=labels)),
            meeting_pick=s(enum=labels + ["none"]),
            could_tell_apart=b("Could you tell these vendors apart on what they offer?"),
            vendors=arr(obj(label=s(enum=labels), stands_out=i(lo=1, hi=7), one_line=s())),
        ),
    )


def _mask(text, cfg):
    names = ["Nebius AI Cloud", "Nebius Token Factory", "Token Factory", "Nebius"]
    for meta in cfg["competitors_cfg"]["companies"].values():
        names += meta["aliases"]
    for n in sorted(set(names), key=len, reverse=True):
        text = re.sub(r"(?<![\w-])" + re.escape(n) + r"(?![\w-])", "[Vendor]", text, flags=re.I)
    return text.replace("™", "").replace("®", "")


def blind_set(cfg, lib, pulse):
    """Nebius claims plus N competitor excerpts, shuffled into Vendor A, B, C."""
    meta = pulse["meta"]
    ours = "\n".join("> " + c["text"] for c in meta["claims"] if c["id"] != meta["canary_id"])
    picks = []
    for comp in pulse.get("competitors") or cfg["competitors_cfg"]["sets"].get(meta["product_line"], []):
        e = lib.best(comp, meta["asset_type"])
        if e:
            picks.append((comp, e))
        if len(picks) >= cfg["committee"]["blind_competitors"]:
            break
    vendors = [{"company": "Nebius", "text": ours, "entry_id": None, "url": None}]
    vendors += [{"company": c, "text": e.text(8), "entry_id": e.eid, "url": e.url, "title": e.title, "date": e.date}
                for c, e in picks]
    random.shuffle(vendors)
    for n, v in enumerate(vendors):
        v["label"] = "Vendor " + "ABCDE"[n]
        v["masked"] = _mask(v["text"], cfg)
    return vendors


def _items_for(pulse, pid):
    rows = []
    for it in pulse.get("items", []):
        if pid in it["persona_ids"]:
            when = it["date"] or f"within the last {it['window_days']} days"
            tag = " [forum sentiment, not fact]" if it["tier"] == 3 else ""
            rows.append(f"{it['id']}: {it['headline']}{tag} ({it['source']}, {when}). {it['why']}")
    return "\n".join(rows) or "Nothing new surfaced for you this month."


def prompt_for(p, pulse, asset_text, vendors, probe=False):
    meta = pulse["meta"]
    claims = "\n".join(f"{c['id']}: {c['text']}" for c in meta["claims"])
    blind = "\n\n".join(f"{v['label']}:\n{v['masked']}" for v in vendors)
    lead = ("Note from the requester: the marketing team is really proud of this copy and thinks it is our best yet.\n\n"
            if probe else "")
    return (f"{lead}THIS WEEK IN YOUR WORLD\n{_items_for(pulse, p.pid)}\n\n"
            f"THE COPY UNDER REVIEW ({meta['title']})\n{asset_text[:7000]}\n\n"
            f"NUMBERED CLAIMS\n{claims}\n\n"
            f"BLIND COMPARISON (names removed)\n{blind}")


def system_for(p):
    return (p.agent_block + "\n\n" + SESSION_RULES + "\nWHAT KEEPS YOU UP AT NIGHT (from your file)\n" + p.concerns[:2500] +
            "\n\nHOW YOU TALK (real quotes from people in your role)\n" + p.voice[:2500] +
            "\n\nSCORING ANCHORS\n" + C.reference("rubric.md"))


def run(engine, people, pulse, asset_text, vendors, probe=False):
    labels = [v["label"] for v in vendors]
    schema = _schema(labels)
    jobs = [(pid, dict(system=system_for(people[pid]), prompt=prompt_for(people[pid], pulse, asset_text, vendors),
                       schema=schema, tier="fast", label=f"review:{pid}")) for pid in pulse["seat"]]
    out = engine.map(jobs)
    reviews = {k: v for k, v in out.items() if not isinstance(v, Exception)}
    errors = {k: str(v) for k, v in out.items() if isinstance(v, Exception)}
    probe_result = None
    if probe and reviews:
        pid = next(iter(reviews))
        try:
            pr = engine.run(system_for(people[pid]), prompt_for(people[pid], pulse, asset_text, vendors, probe=True),
                            schema, tier="fast", label=f"probe:{pid}")
            probe_result = {"persona": pid, "base": mean_score(reviews[pid]), "flattered": mean_score(pr)}
            probe_result["shift"] = round(probe_result["flattered"] - probe_result["base"], 2)
        except Exception as e:  # the probe is advisory
            probe_result = {"persona": pid, "error": str(e)[:200]}
    return reviews, errors, probe_result


def mean_score(rv):
    return round(sum(rv["scores"][k]["score"] for k in CRITERIA) / len(CRITERIA), 2)
