"""The HTML report: three parts (the score, the conversation, the rewrites) and a collapsible appendix."""
import base64
import re
from html import escape as E
from pathlib import Path

from . import config as C
from .judge import PILLARS
from .review import CRITERIA, LABELS
from .util import norm

STATUS = {"recommended": "Recommended", "blocked_by_buyer": "Blocked by a buyer",
          "users_prefer_original": "Users preferred the original", "failed_checks": "Failed checks"}
OVERLAP = {"table_stakes": "Everyone says this", "contested": "Contested", "open_lane": "Open lane"}
PILLAR_STATUS = {"lands": "Lands", "weak": "Weak", "missing": "Missing"}
SCALE = ('<div class="scale"><span>Score key, out of 7:</span>' + "".join(
    f'<span class="sc s{n}">{n}</span>' for n in range(1, 8)) + '<span>1 stop reading · 4 neutral · 7 would forward it</span></div>')


# ---- small helpers -----------------------------------------------------------

def _noid(text):
    """Strip internal ids (Q12, R4, N7, M3 in parentheses) that a model may leave in prose."""
    text = re.sub(r"\s*\((?:Q|R|N)\d+(?:,\s*(?:Q|R|N)\d+)*\)", "", text or "")
    return re.sub(r"\b(?:Q|R|N)\d+\b\s*", "", text).replace(" ,", ",").replace(" .", ".")


def _names(text, names):
    """Older runs debated as Member A, B, C. Readers see real names."""
    return re.sub(r"\bMembers? ([A-C])(?:,? and ([A-C]))?\b",
                  lambda m: names.get(m.group(1), m.group(0)) + (f" and {names.get(m.group(2), m.group(2))}" if m.group(2) else ""),
                  text)


PERSONA_URL = ""


def _plink(p, text=None):
    """A persona's name, linked to its entry on the Confluence persona page when one is configured."""
    label = E(text or p.name)
    return f'<a class="plink" href="{E(PERSONA_URL)}#{p.pid}" target="_blank" rel="noopener">{label}</a>' if PERSONA_URL else label


def _sc(n):
    return f'<span class="sc s{int(n)}">{int(n)}</span>' if n is not None else '<span class="sc sx">·</span>'


def _avg_sc(x):
    if x is None:
        return '<span class="sc sx">·</span>'
    return f'<span class="sc s{max(1, min(7, round(x)))}">{x:.1f}</span>'


def _chips(ids, items):
    out = []
    for x in ids or []:
        it = items.get(x)
        if not it:
            continue
        when = it["date"] or f"last {it['window_days']} days"
        cls = "chip forum" if it["tier"] == 3 else "chip"
        label = f"{it['source']} · {when}"
        out.append(f'<a class="{cls}" href="{E(it["url"] or "#")}" target="_blank" rel="noopener">{E(label)}</a>'
                   if it.get("url") else f'<span class="{cls}">{E(label)}</span>')
    return "".join(out)


def _quote(q):
    if not q:
        return ""
    src = f'{E(q["company"])}, <a href="{E(q["url"])}" target="_blank" rel="noopener">{E(q["title"] or q["url"])}</a>'
    when = "live page, " + q["date"] if q["origin"] == "live" else (q["date"] or "library")
    return f'<blockquote>&ldquo;{E(q["quote"])}&rdquo;<cite>{src} ({E(when)})</cite></blockquote>'


def _nebius(pid, pool, quote=None):
    p = pool.get(pid)
    if not p:
        return ""
    text = quote or p["text"][:220]
    title = E(p["title"].replace(" | Nebius", ""))
    ref = f'<a href="{E(p["url"])}" target="_blank" rel="noopener">{title}</a>' if p.get("url") else f"{title} (internal)"
    return (f'<div class="backed">&ldquo;{E(text)}&rdquo;<cite>Nebius {E(p["kind"])}: {ref}'
            f'{", " + E(p["date"]) if p.get("date") else ""}</cite></div>')


def _numbering(pulse):
    """Marker numbers follow the order messages appear on the asset (canary excluded)."""
    meta = pulse["meta"]
    return {c["id"]: n for n, c in enumerate([c for c in meta["claims"] if c["id"] != meta["canary_id"]], 1)}


# ---- page 1: the score -------------------------------------------------------

def _asset_frame(ctx, nums):
    pulse = ctx["pulse"]
    snap = pulse.get("snapshot")
    rd = ctx["run_dir"]
    src = pulse["source"]
    if snap and (rd / snap["image"]).exists():
        b64 = base64.b64encode((rd / snap["image"]).read_bytes()).decode()
        found = len(snap.get("boxes", {}))
        return (f'<div class="asset-frame"><div class="bar"><span>{E(src)}</span><span>{found} of {len(nums)} messages pinned</span></div>'
                f'<div class="asset-scroll"><img alt="The asset, annotated" src="data:image/jpeg;base64,{b64}"></div></div>')
    # text assets: the text in a light frame, with the same numbered markers
    text = ctx.get("asset_text", "")
    lines = _clean_lines(text)
    claims = {c["id"]: c["text"] for c in pulse["meta"]["claims"] if c["id"] in nums}
    used, html_lines = set(), []
    for ln in lines:
        body, is_head = ln
        out = E(body)
        for cid, ctext in claims.items():
            if cid in used:
                continue
            key = norm(ctext)[:40]
            if key and key in norm(body):
                out = f'<mark class="m"><span class="pin">{nums[cid]}</span>{out}</mark>'
                used.add(cid)
                break
        html_lines.append(f'<p class="{"hd" if is_head else ""}">{out}</p>')
    unplaced = [cid for cid in claims if cid not in used]
    if unplaced:
        html_lines.append('<p class="note">Also reviewed: ' + " ".join(
            f'<mark class="m"><span class="pin">{nums[c]}</span>{E(claims[c])}</mark>' for c in unplaced) + '</p>')
    return (f'<div class="asset-frame"><div class="bar"><span>{E(src)}</span><span>text version</span></div>'
            f'<div class="asset-scroll"><div class="textframe">{"".join(html_lines[:90])}</div></div></div>')


def _clean_lines(text):
    out = []
    for raw in text.splitlines():
        s = raw.strip()
        if not s or re.fullmatch(r"[\|\-\s:]+", s):
            continue
        is_head = s.startswith("#")
        s = s.lstrip("#").strip()
        if s.startswith("|"):
            for cell in [c.strip() for c in s.strip("|").split("|")]:
                if cell:
                    out.append((re.sub(r"[ᵃ-ᶿ⁰-₟]+", "", cell), False))
            continue
        s = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", s)
        s = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", s).replace("\\*", "*")
        if s:
            out.append((s, is_head))
    return out


def page1(ctx):
    people, pulse, N, J = ctx["people"], ctx["pulse"], ctx["numbers"], ctx["judge"]
    nums = _numbering(pulse)
    notes = {x["claim_id"]: x["note"] for x in J["message_notes"]}
    rows = {r["id"]: r for r in N["grid"]}
    h = ['<section class="page" id="score"><div class="wrap"><div class="pnum">1 · The score</div>',
         '<h2>How each message lands</h2>',
         '<p class="lede">Numbers on the page match the list. Each score is <b>out of 7</b>, averaged for the people who build with it (users) '
         'and the people who approve and sign (buyers).</p>' + SCALE]
    if pulse.get("banner"):
        h.append(f'<div class="banner">{E(pulse["banner"])}</div>')
    h.append('<div class="score-layout">' + _asset_frame(ctx, nums) + '<div class="notes">')
    for cid in sorted(nums, key=lambda c: nums[c]):
        r = rows.get(cid)
        if not r:
            continue
        veto = f' <span class="tag t-veto">Vetoed by {E(", ".join(people[x].name for x in r["vetoes"]))}</span>' if r["vetoes"] else ""
        h.append(f'<div class="nrow"><span class="pin">{nums[cid]}</span><div><div class="lab">{E(r["label"])}{veto}</div>'
                 f'<div class="msg">{E(r["text"])}</div><div class="crit">{E(_noid(notes.get(cid, "")))}</div></div>'
                 f'<div class="scores">Users /7 {_avg_sc(r["users"])}Buyers /7 {_avg_sc(r["buyers"])}</div></div>')
    h.append('</div></div>')
    # value pillars
    if J.get("pillars"):
        h.append('<div class="pillars"><h3>Value pillars: does the asset make them shine?</h3><div class="grid g3">')
        for p in J["pillars"]:
            h.append(f'<div class="panel pill-card"><span class="tag t-{p["status"]}">{PILLAR_STATUS[p["status"]]}</span>'
                     f'<p class="pn">{E(PILLARS[p["pillar"]])}</p><p>{E(_noid(p["line"]))}</p></div>')
        h.append('</div></div>')
    # the grid: messages ranked, one column per persona
    seat_u, seat_b = N["users"], N["buyers"]
    h.append('<h3>The grid: every message, every persona</h3><p class="note"><b>Scores are out of 7</b> '
             '(7: would forward the page for this line · 4: neutral · 1: would stop reading). Ranked by users first, then buyers. '
             'A dark tag means a buyer would stop the deal on that line.' + (f' <a href="{E(PERSONA_URL)}" target="_blank" rel="noopener">Who are these personas?</a>' if PERSONA_URL else '') + '</p>' + SCALE + '<div class="scroll"><table><tr>'
             '<th class="l">#</th><th class="l">Message</th>')
    for n, pid in enumerate(seat_u + seat_b):
        sep = ' class="gsep"' if n == len(seat_u) else ""
        h.append(f'<th{sep}>{_plink(people[pid])}<span class="r">{E(people[pid].role_label)}</span></th>')
    h.append('<th class="gsep">Users<span class="r">avg /7</span></th><th>Buyers<span class="r">avg /7</span></th></tr>')
    for cid in N["ranked"]:
        r = rows[cid]
        h.append(f'<tr><td class="l"><span class="pin">{nums.get(cid, "")}</span></td>'
                 f'<td class="l msgcell"><b>{E(r["label"])}</b><span>{E(r["text"][:110] + ("…" if len(r["text"]) > 110 else ""))}</span></td>')
        for n, pid in enumerate(seat_u + seat_b):
            sep = ' class="gsep"' if n == len(seat_u) else ""
            h.append(f'<td{sep}>{_sc(r["scores"].get(pid))}</td>')
        h.append(f'<td class="gsep">{_avg_sc(r["users"])}</td><td>{_avg_sc(r["buyers"])}'
                 + (' <span class="tag t-veto">veto</span>' if r["vetoes"] else "") + '</td></tr>')
    h.append('</table></div></div></section>')
    return "".join(h)


# ---- page 2: the conversation --------------------------------------------------

def _slack_text(text):
    out = []
    for ln in text.split("\n"):
        if ln.strip().startswith(">"):
            out.append(f'<span class="q">{E(ln.strip()[1:].strip())}</span>')
        else:
            out.append(E(ln))
    return "\n".join(out).strip()


def page2(ctx):
    people, pulse, debate = ctx["people"], ctx["pulse"], ctx["debate"]
    items = {it["id"]: it for it in pulse.get("items", [])}
    h = ['<section class="page" id="talk"><div class="wrap"><div class="pnum">2 · The conversation</div>',
         '<h2>What they said to each other</h2>',
         '<p class="lede">After scoring alone, the committee talked it through. Every message is synthetic, written in the voice of a '
         'composite persona built from real quotes by people in that role.</p>']
    if not debate:
        h.append('<p class="note">Only one persona was seated, so there was no conversation.</p></div></section>')
        return "".join(h)
    h.append(f'<div class="slack"><div class="ch"># vendor-review <span>{len(debate)} threads · {len(ctx["reviews"])} members</span></div>')
    minute = 2
    for th in debate:
        h.append(f'<div class="thread"><div class="thead">Thread <b>{E(th.get("topic") or th.get("question", ""))}</b></div>')
        if th.get("fact_note"):
            np_ = pulse.get("nebius", {}).get("pool", {}).get(th.get("fact_id") or "", {})
            link = (f' <a href="{E(np_["url"])}" target="_blank" rel="noopener">{E(np_.get("date") or "source")}</a>' if np_.get("url") else "")
            h.append(f'<div class="factcheck"><b>Fact check</b> {E(_noid(th["fact_note"]))}{link}</div>')
        turns = th.get("turns", [])
        names = {t.get("member"): people[t["persona"]].name for t in turns if t.get("member")}
        agreed = {}
        for t in turns:
            for nm in t.get("agrees_with", []) or []:
                agreed.setdefault(nm.strip().split()[0], []).append(people[t["persona"]].name)
        for t in turns:
            p = people[t["persona"]]
            minute += 1
            txt = _names(t["text"], names)
            reacts = agreed.get(p.name, [])
            react_html = (f'<div class="reacts"><span class="react">&#128077; {len(reacts)} · {E(", ".join(dict.fromkeys(reacts)))}</span></div>'
                          if reacts else "")
            moved = ""
            sc = t.get("score_change") or {}
            if sc.get("changed") == "yes" and sc.get("from") is not None and sc["from"] != sc["new_score"]:
                moved = (f'<div class="moved">{E(p.name)} moved <b>{E(LABELS[sc["criterion"]])}</b> from {sc["from"]} to '
                         f'{sc["new_score"]}</div>')
            initials = "".join(w[0] for w in p.name.split())[:2].upper()
            h.append(f'<div class="msgrow"><div class="av {p.group}">{E(initials)}</div><div>'
                     f'<div class="who">{_plink(p)}<span class="r">{E(p.role_label)}</span><span class="t">10:{minute:02d}</span></div>'
                     f'<div class="txt">{_slack_text(txt)}</div>{_chips(t.get("pulse_used"), items)}{react_html}{moved}</div></div>')
        h.append('</div>')
    h.append('</div></div></section>')
    return "".join(h)


# ---- page 3: the rewrites ------------------------------------------------------

def page3(ctx):
    people, rws, pool, J, pulse = ctx["people"], ctx["rewrites"], ctx["pool"], ctx["judge"], ctx["pulse"]
    npool = pulse.get("nebius", {}).get("pool", {})
    nfacts = {x["passage_id"]: x.get("quote") for x in pulse.get("nebius", {}).get("supports", []) + pulse.get("nebius", {}).get("unused", [])
              + pulse.get("nebius", {}).get("standing", [])}
    nums = _numbering(pulse)
    rows = {r["id"]: r for r in ctx["numbers"]["grid"]}
    h = ['<section class="page" id="rewrites"><div class="wrap"><div class="pnum">3 · The rewrites</div>',
         '<h2>What to write instead</h2>',
         '<p class="lede">The Nebius marketing writer rewrote the weakest lines, backed by what Nebius has already published. '
         'The committee then compared old and new blind. Users picked the winner. Any buyer could block a line they did not believe.</p>']
    if not rws:
        h.append('<p>No lines needed rewriting.</p>')
    for rw in rws:
        v = rw["vote"]
        u = v["users"]
        r = rows.get(rw["claim_id"], {})
        pill = PILLARS.get(rw.get("pillar") or r.get("pillar", ""), "")
        h.append(f'<div class="rw"><div class="top"><span class="pin">{nums.get(rw["claim_id"], "")}</span>'
                 f'<span class="lab">{E(r.get("label", ""))}</span><span class="tag t-{v["status"]}">{STATUS[v["status"]]}</span>'
                 + (f'<span class="tag t-weak" style="background:#EEF4FF;color:var(--deep)">{E(pill)}</span>' if pill else "")
                 + (f'<span class="note">{rw["words"]} words</span>' if rw.get("words") else "")
                 + f'<span class="note">Score out of 7 <span class="delta">{v["before"]} &rarr; {v["after"]}</span> · users {u["new"]}-{u["old"]} for the new line'
                 + (f' · blocked by {E(", ".join(people[x].name for x in v["vetoes"]))}' if v["vetoes"] else "") + '</span></div>'
                 f'<p class="before">{E(rw["original"])}</p><div class="afterrow"><p class="after">{E(rw["proposed"])}</p>'
                 + (f'<div class="tile"><span class="fig">{E(rw["tile_figure"])}</span><span class="tl">{E(rw.get("tile_label") or "")}</span></div>'
                    if rw.get("tile_figure") else "") + '</div>'
                 f'<p class="kv"><b>Why:</b> {E(_noid(rw["why"]))}</p>')
        for sid in rw.get("support_ids", [])[:2]:
            h.append(_nebius(sid, npool, nfacts.get(sid)))
        if rw.get("also_proof"):
            spare = [re.sub(r"^\s*[:,-]\s*", "", _noid(x)) for x in rw["also_proof"][:3]]
            h.append('<p class="kv"><b>Other proof that fits (left out to keep one proof per line):</b> ' + E("; ".join(spare)) + '</p>')
        if rw["placeholders"]:
            h.append('<p class="kv"><b>Fill before publishing:</b> ' + E("; ".join(rw["placeholders"])) + '</p>')
        if rw["issues"]:
            h.append('<p class="kv"><b>Checks that failed:</b> ' + E("; ".join(rw["issues"])) + '</p>')
        h.append('</div>')
    if J.get("unused_proof"):
        h.append('<h3>Proof you already have but are not using</h3><div class="grid g3">')
        for u in J["unused_proof"]:
            h.append(f'<div class="panel"><p class="kv" style="margin-top:0">{E(_noid(u["line"]))}</p>{_nebius(u["passage_id"], npool, nfacts.get(u["passage_id"]))}</div>')
        h.append('</div>')
    if J.get("corrections"):
        h.append('<h3>Checked against Nebius&rsquo;s own record</h3><p class="note">Where a reviewer assumed something about Nebius '
                 'that our published record contradicts. The critique still stands if the page does not show it.</p><ul class="tight">')
        for c in J["corrections"]:
            p = npool.get(c["passage_id"], {})
            h.append(f'<li><b>{E(c["who"])}</b> assumed {E(c["assumed"])} Actually: {E(c["actually"])} '
                     f'<a class="chip" href="{E(p.get("url", "#"))}" target="_blank" rel="noopener">{E((p.get("date") or "") + " source")}</a></li>')
        h.append('</ul>')
    h.append('</div></section>')
    return "".join(h)


# ---- appendix -------------------------------------------------------------------

def _app(title, body, open_=False):
    return f'<details class="app"{" open" if open_ else ""}><summary>{E(title)}</summary><div class="inner">{body}</div></details>'


def appendix(ctx):
    people, N, J, pulse, pool, vendors, rv = ctx["people"], ctx["numbers"], ctx["judge"], ctx["pulse"], ctx["pool"], ctx["vendors"], ctx["reviews"]
    parts = []
    # A. competitive view
    b = N["blind"]
    claims = {c["id"]: c["text"] for c in pulse["meta"]["claims"]}
    comp = [f'<p>{E(_noid(J["blind_story"]))}</p><div class="grid g3">',
            f'<div class="panel stat"><div class="v">{b["avg_rank"] if b["avg_rank"] is not None else "n/a"}</div><div class="l">Our average rank of {b["vendors"]} (1 is best)</div></div>',
            f'<div class="panel stat"><div class="v">{b["meeting_picks"].get("Nebius", 0)} of {b["n"]}</div><div class="l">Would take our meeting first</div></div>',
            f'<div class="panel stat"><div class="v">{b["could_not_tell_apart"]} of {b["n"]}</div><div class="l">Could not tell the vendors apart</div></div></div>',
            '<h3>Who was behind each label</h3><ul class="tight">']
    for v in sorted(vendors, key=lambda v: v["label"]):
        comp.append(f'<li>{E(v["label"])}: <b>{E(v["company"])}</b> · stands out {b["stands_out"].get(v["company"], "")} · '
                    f'{b["meeting_picks"].get(v["company"], 0)} meeting picks'
                    + (f' · <a href="{E(v["url"])}" target="_blank" rel="noopener">what they saw</a>' if v.get("url") else "") + '</li>')
    comp.append('</ul>')
    if J["overlap"]:
        comp.append('<h3>Who else says it</h3>')
        for o in J["overlap"]:
            comp.append(f'<p style="margin:16px 0 4px"><span class="tag t-{o["status"]}">{OVERLAP[o["status"]]}</span> '
                        f'<b style="color:var(--deep)">{E(claims.get(o["claim_id"], ""))}</b></p><p class="kv">{E(_noid(o["explanation"]))}</p>'
                        + "".join(_quote(pool.get(q)) for q in o["quote_ids"][:2]))
    if J["patterns"]:
        comp.append('<h3>Patterns worth borrowing</h3><div class="grid g2">')
        for p in J["patterns"]:
            comp.append(f'<div class="panel"><b style="color:var(--deep)">{E(p["title"])}</b>{_quote(pool.get(p["quote_id"]))}<p class="kv">{E(_noid(p["explanation"]))}</p></div>')
        comp.append('</div>')
    changes = [c for c in pulse.get("competitor_changes", []) if c["change"] and not c["change"].lower().startswith("no material")]
    if changes:
        comp.append('<h3>Competitor pages that changed since the Sept 28 library</h3><ul class="tight">')
        for c in changes:
            comp.append(f'<li><b>{E(c["company"])}</b>: {E(c["change"])}' + (f' Now reads: &ldquo;{E(c["new_line"])}&rdquo;' if c.get("new_line") else "") + '</li>')
        comp.append('</ul>')
    parts.append(_app("A · Competitive view: blind test and who else says it", "".join(comp)))
    # B. market pulse
    items = pulse.get("items", [])
    mp = ['<ul class="tight">'] + [
        f'<li>{E(it["headline"])} <span class="note">{E(it["why"])}</span> {_chips([it["id"]], {it["id"]: it})}</li>' for it in items] + ['</ul>']
    parts.append(_app(f"B · Market pulse: {len(items)} live items the committee saw", "".join(mp) if items else "<p>None.</p>"))
    # C. persona scores
    ps = ['<p class="note"><b>Scores are out of 7.</b></p><div class="scroll"><table><tr><th class="l">Persona</th>' + "".join(f"<th>{E(LABELS[k])}</th>" for k in CRITERIA)
          + '<th>Average</th><th>Meeting?</th><th class="l">Stopping objection</th></tr>']
    for pid in N["ranking"]:
        r = rv[pid]
        ps.append(f'<tr><td class="l"><b style="color:var(--deep)">{_plink(people[pid])}</b> <span class="note">{E(people[pid].role_label)}</span></td>'
                  + "".join(f"<td>{_sc(r['scores'][k]['score'])}</td>" for k in CRITERIA)
                  + f'<td>{_avg_sc(N["per_persona"][pid]["mean"])}</td><td><span class="tag t-{r["meeting"]}">{r["meeting"].title()}</span></td>'
                  f'<td class="l note">{E(r["stopping_objection"]["text"])}</td></tr>')
    ps.append('</table></div><h3>Each persona&rsquo;s one recommendation</h3><ul class="tight">')
    ps += [f'<li><b>{E(people[pid].name)}</b>: {E(rv[pid]["key_recommendation"])}</li>' for pid in N["ranking"]]
    ps.append('</ul>')
    parts.append(_app("C · Persona scores, objections and recommendations", "".join(ps)))
    # D. honesty checks and product issues
    cn = N["canary"]
    hc = [f'<p><b>Canary test:</b> {"Passed" if cn["pass"] else "Failed"}. {cn["flagged_weak"]} of {cn["n"]} personas marked a deliberately weak test line as weak or failing.</p>']
    pr = ctx.get("probe")
    if pr and "shift" in pr:
        hc.append(f'<p><b>Flattery probe:</b> telling {E(people[pr["persona"]].name)} "the team loves this" moved the average by {pr["shift"]:+}.</p>')
    prod = [i for i in J.get("issues", []) if i["kind"] == "product"]
    if prod:
        hc.append('<p><b>Problems copy alone cannot fix:</b></p><ul class="tight">' + "".join(
            f'<li>{E(i["line"])} <span class="note">Owner: {E(i["owner"])}</span></li>' for i in prod) + '</ul>')
    parts.append(_app("D · Honesty checks and product problems", "".join(hc)))
    # E. method and limits
    nb = pulse.get("nebius", {})
    me = ['<ol class="tight">',
          f'<li><b>Nebius fact sweep.</b> {nb.get("corpus_size", 0)} passages from Nebius blog posts and press releases, plus a live search of nebius.com, '
          'checked every message before the committee met.</li>',
          '<li><b>Market pulse.</b> Tavily searched where each persona reads (30 days) and competitor newsrooms (90 days), and checked live competitor pages.</li>',
          '<li><b>Private reviews.</b> Each persona scored every message alone, in its own model session, then ranked a blind comparison against competitor copy.</li>',
          '<li><b>Conversation.</b> A Slack-style thread. Each message is its own model call that sees the thread so far.</li>',
          '<li><b>Judge.</b> Code computed every score, rank and veto. A model wrote the summaries, quoting only verified excerpts.</li>',
          '<li><b>Rewrites.</b> The Nebius marketing writer, checked for copied wording, unsourced numbers and house-rule errors, then re-voted blind.</li></ol>',
          '<p><b>Limits.</b> The personas are composites built from 334 real quotes, not real buyers, and not yet calibrated against real buyers. '
          '<b>Nebius has no call recordings or customer interview corpus</b>, so what our own buyers say on calls is not in them yet. '
          'Synthetic committees find objections well and predict winners poorly.</p>',
          f'<p class="note">Run {E(ctx["run"]["run_id"])} · {E(ctx["run"]["date"])} · engine {E(ctx["run"]["engine"])} · {ctx["run"]["model_calls"]} model calls · '
          f'{ctx["run"]["tavily_calls"]} Tavily calls ({ctx["run"]["tavily_cached"]} cached) · reported model cost ${ctx["run"]["cost"]}</p>']
    parts.append(_app("E · Method and limits", "".join(me)))
    # F. sources
    parts.append(_app("F · Every source: Nebius record, market sweep and competitor pages", sources_section(ctx)))
    return ('<section class="page" id="appendix"><div class="wrap"><div class="pnum">Appendix</div><h2>The detail behind it</h2>'
            + "".join(parts) + '</div></section>')


def sources_section(ctx):
    from .pulse import source_rows
    pulse = ctx["pulse"]
    rows = source_rows(pulse, ctx["people"])
    npool = pulse.get("nebius", {}).get("pool", {})
    h = []
    if npool:
        seen = {}
        for p in npool.values():
            seen.setdefault(p["url"], p)
        h.append(f'<p class="kv"><b>Nebius published record</b> ({len(seen)})</p><ul class="tight">')
        for p in sorted(seen.values(), key=lambda p: p.get("date") or "", reverse=True):
            h.append(f'<li><a href="{E(p["url"])}" target="_blank" rel="noopener">{E(p["title"].replace(" | Nebius", ""))}</a> '
                     f'<span class="note">{E(p["kind"])}{" · " + E(p["date"]) if p.get("date") else ""}</span></li>')
        h.append('</ul>')
    order = [("persona reading list", "Where the personas read (last 30 days)"), ("market news", "Market news (last 30 days)"),
             ("competitor newsroom", "Competitor newsrooms and blogs (last 90 days)"),
             ("competitor page checked", "Competitor pages checked against the Sept 28 library")]
    for key, title in order:
        grp = [r for r in rows if r["group"] == key]
        if not grp:
            continue
        h.append(f'<p class="kv" style="margin-top:16px"><b>{E(title)}</b> ({len(grp)})</p><ul class="tight">')
        for r in grp:
            meta = [r["source"]] + ([r["date"]] if r["date"] else []) + (["forum sentiment"] if str(r["tier"]) == "3" else [])
            h.append(f'<li><a href="{E(r["url"])}" target="_blank" rel="noopener">{E(r["title"] or r["url"])}</a> '
                     f'<span class="note">{E(" · ".join(meta))}</span></li>')
        h.append('</ul>')
    h.append('<p class="note">Also saved as sources.csv in the run folder and added to the running sources ledger.</p>')
    return "".join(h)


def render(ctx):
    global PERSONA_URL
    PERSONA_URL = ctx.get("persona_page_url") or ""
    pulse, J = ctx["pulse"], ctx["judge"]
    m = pulse["meta"]
    header = (f'<header class="top"><div class="wrap"><div class="brand"><div class="wordmark">nebius<span>.</span> persona committee</div>'
              f'<span class="pill-internal">Internal use only</span></div>'
              f'<div class="kicker">Committee review · {E(m["title"])}</div><h1>{E(J["verdict"])}</h1>'
              f'<div class="wff"><div><b>What works</b>{E(_noid(J["works"]))}</div><div><b>What fails</b>{E(_noid(J["fails"]))}</div>'
              f'<div><b>The one fix</b>{E(_noid(J["fix"]))}</div></div>'
              f'<div class="meta">{E(ctx["run"]["date"])} · {len(ctx["reviews"])} personas · {E(pulse["source"])}</div></div></header>'
              '<nav class="pages"><div class="wrap"><a href="#score">1 The score</a><a href="#talk">2 The conversation</a>'
              '<a href="#rewrites">3 The rewrites</a><a href="#appendix">Appendix</a></div></nav>')
    body = header + page1(ctx) + page2(ctx) + page3(ctx) + appendix(ctx) + \
        '<footer><div class="wrap">Nebius Persona Committee · synthetic feedback for internal message testing · not buyer research</div></footer>'
    tpl = (C.SKILL_DIR / "templates" / "report.html").read_text()
    return tpl.replace("{{TITLE}}", E("Committee Review: " + m["title"])).replace("{{BODY}}", body)
