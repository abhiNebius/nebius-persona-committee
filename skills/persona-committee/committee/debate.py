"""Stage 2: the conversation. A Slack-style thread among the committee, after private scores are locked.

A planner picks three threads (the most disputed message, a live market or competitor moment, and a
believability test). A persona starts each thread by quoting the line; others reply in turn, by name,
seeing the thread so far. People can come back in. Every message is its own isolated model call.
"""
from concurrent.futures import ThreadPoolExecutor

from . import config as C
from . import nebius as NB
from .review import CRITERIA, system_for
from .util import arr, i, obj, s

PLAN_SCHEMA = obj(threads=arr(obj(
    topic=s("Three to six words, e.g. 'The 112% TCO line'"),
    claim_id=s(nullable=True),
    pulse_id=s("A live item worth bringing in, or null", nullable=True),
    fact_note=s("If this thread touches something Nebius has published that the page does not show (for example a rating "
                "a competitor also claims), one plain sentence a reader should know, citing the fact. Otherwise null", nullable=True),
    fact_id=s("N id of that fact, or null", nullable=True),
    speakers=arr(s("Persona id in speaking order; 4 to 6 turns; the opener may speak again later")),
)))

TURN_SCHEMA = obj(
    text=s("Your Slack message: one to three short sentences, 45 words at most"),
    agrees_with=arr(s("First names of people in the thread whose point you agree with (they get a reaction)")),
    score_change=obj(changed=s(enum=["yes", "no"]), criterion=s(enum=CRITERIA), new_score=i(lo=1, hi=7),
                     why=s("Why you moved, or empty")),
    pulse_used=arr(s()),
)


def _summary(people, reviews):
    rows = []
    for pid, rv in reviews.items():
        cl = "; ".join(f"{c['claim_id']} {c['score']}/7" for c in rv["claims"])
        rows.append(f"{pid} {people[pid].display} ({people[pid].group}): {cl}. Stop: {rv['stopping_objection']['text']}")
    return "\n".join(rows)


def plan(engine, people, pulse, reviews):
    items = "\n".join(f"{it['id']}: {it['headline']} ({it['source']})" for it in pulse.get("items", []))
    claims = "\n".join(f"{c['id']}: {c['text']}" for c in pulse["meta"]["claims"] if c["id"] != pulse["meta"]["canary_id"])
    users = [x for x in reviews if people[x].group == "users"]
    buyers = [x for x in reviews if people[x].group == "buyers"]
    system = ("You plan three Slack threads for a buying committee reviewing a vendor's page. Thread 1: the message they "
              "disagree about most. Thread 2: a moment from the live market or a competitor move (give its pulse id), or the "
              "weakest message. Thread 3: a believability test, where a buyer pushes on something the users liked. Each thread "
              "has 4 to 6 turns. Mix users and buyers. The person who starts should hold a strong view; someone who disagrees "
              "should speak second; the opener may come back later. Never build a thread on a premise that contradicts the "
              "VERIFIED NEBIUS FACTS. No em-dashes.")
    prompt = (f"MESSAGES\n{claims}\n\nPRIVATE SCORES\n{_summary(people, reviews)}\n\nLIVE ITEMS\n{items or 'none'}\n\n"
              f"VERIFIED NEBIUS FACTS\n{NB.brief(pulse.get('nebius', {}))}\n\nUSERS: {users}\nBUYERS: {buyers}")
    out = engine.run(system, prompt, PLAN_SCHEMA, tier="deep", label="thread:plan")
    threads = []
    for th in out["threads"][:3]:
        sp = [x for x in th["speakers"] if x in reviews][:6]
        if len(sp) < 3:
            sp = (users[:2] + buyers[:2])[:4] or list(reviews)[:4]
        th["speakers"] = sp
        threads.append(th)
    return threads


def _run_thread(engine, people, pulse, reviews, th):
    claims = {c["id"]: c["text"] for c in pulse["meta"]["claims"]}
    items = {it["id"]: it for it in pulse.get("items", [])}
    line = claims.get(th.get("claim_id") or "", "")
    live = items.get(th.get("pulse_id") or "")
    style = C.reference("conversation-style.md")
    msgs = []
    for n, pid in enumerate(th["speakers"]):
        p, rv = people[pid], reviews[pid]
        so_far = "\n".join(f"{people[m['persona']].name} ({people[m['persona']].role_label}): {m['text']}" for m in msgs)
        mine = next((c for c in rv["claims"] if c["claim_id"] == th.get("claim_id")), None)
        openers = [m["text"].split()[0].lower().strip(",.:") for m in msgs[1:] if m.get("text")]
        used_at = any(o.startswith("@") for o in openers)
        used_same = any(o in ("same", "agree", "agreed", "+1", "fair", "yes", "yeah") for o in openers)
        task = ("Start the thread. Quote the line with > and say what you think."
                if n == 0 else "Reply in the thread. React to what was just said.")
        if n > 0:
            if used_at:
                task += " Do NOT start with an @mention; someone already did. Start with the point."
            if used_same:
                task += " Do NOT start with 'same', 'agree', '+1', 'fair' or 'yes'."
        if live and n in (0, 1):
            task += f" You saw this recently and may bring it up: {live['headline']} ({live['source']}). Its id is {live['id']}."
        prompt = f"CHANNEL: #vendor-review. Someone shared a vendor's page. Thread topic: {th['topic']}.\n"
        if line:
            prompt += f"THE LINE: {line}\n"
        if mine:
            prompt += f"YOUR PRIVATE TAKE: {mine['score']}/7, {mine['why']}\n"
        prompt += f"\nTHREAD SO FAR\n{so_far or '(empty)'}\n\nYOUR TURN: {task}"
        system = system_for(p) + "\n\nSLACK STYLE\n" + style
        try:
            t = engine.run(system, prompt, TURN_SCHEMA, tier="fast", label=f"thread:{pid}")
        except Exception as e:
            t = {"text": "", "error": str(e)[:200]}
        t["persona"] = pid
        sc = t.get("score_change") or {}
        if sc.get("changed") == "yes":
            sc["from"] = rv["scores"][sc["criterion"]]["score"]
        msgs.append(t)
    return [m for m in msgs if m.get("text")]


def run(engine, people, pulse, reviews):
    if len(reviews) < 2:
        return []
    threads = plan(engine, people, pulse, reviews)
    with ThreadPoolExecutor(max_workers=3) as ex:
        convos = list(ex.map(lambda th: _run_thread(engine, people, pulse, reviews, th), threads))
    for th, msgs in zip(threads, convos):
        th["turns"] = msgs
    return threads
