"""Stage 2: the moderated debate. Runs after private scores are locked.

A moderator picks three points. On each point, three personas speak in turn. Each sees what
earlier speakers said, anonymized as Member A, B, C, because agents conform when they know who
is talking. Names are restored in the report.
"""
from concurrent.futures import ThreadPoolExecutor

from .review import CRITERIA, system_for
from .util import arr, i, obj, s

MOD_SCHEMA = obj(points=arr(obj(
    question=s("One plain sentence the moderator asks the room"),
    context=s("One sentence of context the moderator gives, citing a claim or live item"),
    claim_id=s(nullable=True),
    pulse_id=s(nullable=True),
    speakers=arr(s("Persona id, in speaking order")),
)))

TURN_SCHEMA = obj(
    text=s("What you say, 50 to 110 words, in your voice"),
    responds_to=s("Letter of the member you are answering, or null", nullable=True),
    stance=s(enum=["agree", "disagree", "builds", "new_point"]),
    score_change=obj(changed=s(enum=["yes", "no"]), criterion=s(enum=CRITERIA), new_score=i(lo=1, hi=7),
                     why=s("Why you moved, or empty")),
    pulse_used=arr(s()),
)

TURN_RULES = """
COMMITTEE DEBATE: RULES
- You already gave your private review. Now the committee discusses one point.
- Speak in your own voice. Be direct. Disagree when you disagree. Do not be polite for its own sake.
- You may answer an earlier member by letter ("Member A is right about the contract, but...").
- Change a score only if another member gave you a reason you had not considered. Say which reason.
- Mention live items only by what they say, and list their IDs in pulse_used. Never invent facts.
- 50 to 110 words. No em-dashes.
"""


def _summary(people, reviews):
    rows = []
    for pid, rv in reviews.items():
        p = people[pid]
        sc = ", ".join(f"{k} {rv['scores'][k]['score']}" for k in CRITERIA)
        cl = "; ".join(f"{c['claim_id']} {c['verdict']}" for c in rv["claims"])
        rows.append(f"{pid} {p.display} ({p.group}): {sc}. Claims: {cl}. Stop: {rv['stopping_objection']['text']}. "
                    f"Meeting: {rv['meeting']}. Says: {rv['first_reaction']}")
    return "\n".join(rows)


def moderate(engine, people, pulse, reviews):
    items = "\n".join(f"{it['id']}: {it['headline']} ({it['source']})" for it in pulse.get("items", []))
    comp = "\n".join(f"{c['company']}: {c['change']}" for c in pulse.get("competitor_changes", []))
    claims = "\n".join(f"{c['id']}: {c['text']}" for c in pulse["meta"]["claims"] if c["id"] != pulse["meta"]["canary_id"])
    buyers = [x for x in reviews if people[x].group == "buyers"]
    users = [x for x in reviews if people[x].group == "users"]
    system = ("You moderate a buying committee reviewing marketing copy. Pick exactly 3 discussion points. "
              "Point 1: the claim the committee disagrees about most. Point 2: a challenge from the live market or a "
              "competitor move (cite its pulse id), or the weakest claim if there is none. Point 3: the believability "
              "test, where a business buyer challenges what the users liked. For each point name 3 speakers from the "
              "committee, mixing users and buyers when both are present, the most opposed views first. "
              "Questions are short and concrete. No em-dashes.")
    prompt = (f"CLAIMS\n{claims}\n\nPRIVATE REVIEWS\n{_summary(people, reviews)}\n\nLIVE ITEMS\n{items or 'none'}\n\n"
              f"COMPETITOR CHANGES\n{comp or 'none'}\n\nUSERS: {users}\nBUYERS: {buyers}")
    out = engine.run(system, prompt, MOD_SCHEMA, tier="deep", label="debate:moderator")
    points = []
    for pt in out["points"][:3]:
        sp = [x for x in pt["speakers"] if x in reviews][:3]
        if len(sp) < 2:
            sp = (users[:2] + buyers[:1]) or list(reviews)[:3]
        pt["speakers"] = sp
        points.append(pt)
    return points


def _chain(engine, people, pulse, reviews, point):
    turns = []
    for n, pid in enumerate(point["speakers"]):
        p, rv = people[pid], reviews[pid]
        heard = "\n".join(f"Member {chr(65 + k)}: {t['text']}" for k, t in enumerate(turns)) or "(You speak first.)"
        mine = next((c for c in rv["claims"] if c["claim_id"] == point.get("claim_id")), None)
        prompt = (f"MODERATOR: {point['context']}\nQUESTION: {point['question']}\n\n"
                  f"YOUR PRIVATE REVIEW: {rv['first_reaction']} "
                  + (f"On {mine['claim_id']} you said {mine['verdict']}: {mine['why']} " if mine else "")
                  + f"Your scores: " + ", ".join(f"{k} {rv['scores'][k]['score']}" for k in CRITERIA)
                  + f"\n\nSO FAR IN THIS DISCUSSION\n{heard}\n\nYou are Member {chr(65 + n)}.")
        try:
            t = engine.run(system_for(p) + "\n\n" + TURN_RULES, prompt, TURN_SCHEMA, tier="fast", label=f"debate:{pid}")
        except Exception as e:
            t = {"text": "", "error": str(e)[:200]}
        t["persona"] = pid
        t["member"] = chr(65 + n)
        sc = t.get("score_change") or {}
        if sc.get("changed") == "yes":
            sc["from"] = rv["scores"][sc["criterion"]]["score"]
        turns.append(t)
    return turns


def run(engine, people, pulse, reviews):
    if len(reviews) < 2:
        return []
    points = moderate(engine, people, pulse, reviews)
    with ThreadPoolExecutor(max_workers=3) as ex:
        chains = list(ex.map(lambda pt: _chain(engine, people, pulse, reviews, pt), points))
    for pt, turns in zip(points, chains):
        pt["turns"] = [t for t in turns if t.get("text")]
    return points
