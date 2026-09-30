"""Stage 5: the HTML report. Five pages plus a method appendix, in Nebius colors."""
from html import escape as E

from . import config as C
from .review import CRITERIA, LABELS

STATUS = {"recommended": "Recommended", "blocked_by_buyer": "Blocked by a buyer",
          "users_prefer_original": "Users preferred the original", "failed_checks": "Failed checks"}
OVERLAP = {"table_stakes": "Everyone says this", "contested": "Contested", "open_lane": "Open lane"}


def _chips(ids, items):
    out = []
    for x in ids or []:
        it = items.get(x)
        if not it:
            continue
        when = it["date"] or f"last {it['window_days']} days"
        cls = "chip forum" if it["tier"] == 3 else "chip"
        label = f"{x} · {it['source']} · {when}"
        out.append(f'<a class="{cls}" href="{E(it["url"] or "#")}" target="_blank" rel="noopener">{E(label)}</a>'
                   if it.get("url") else f'<span class="{cls}">{E(label)}</span>')
    return "".join(out)


def _noid(text):
    """Strip internal ids (Q12, R4) that a model may leave in prose."""
    import re as _re
    text = _re.sub(r"\s*\((?:Q|R)\d+(?:,\s*(?:Q|R)\d+)*\)", "", text or "")
    return _re.sub(r"\b(?:Q|R)\d+\b\s*", "", text).replace(" ,", ",").replace(" .", ".")


def _names(text, names):
    """Personas debated as Member A, B, C. Readers see the real names."""
    import re as _re
    text = _re.sub(r"\bMembers? ([A-C])(?:,? and ([A-C]))?\b",
                   lambda m: names.get(m.group(1), m.group(0)) + (f" and {names.get(m.group(2), m.group(2))}" if m.group(2) else ""),
                   text)
    return text


def _who(p):
    return f'<span class="who">{E(p.name)}<span class="role">{E(p.role_label)}</span></span>'


def _score(n):
    return f'<span class="score s{int(n)}">{int(n)}</span>'


def _quote(q):
    if not q:
        return ""
    src = f'{E(q["company"])}, <a href="{E(q["url"])}" target="_blank" rel="noopener">{E(q["title"] or q["url"])}</a>'
    when = "live page, " + q["date"] if q["origin"] == "live" else (q["date"] or "library")
    return f'<blockquote>&ldquo;{E(q["quote"])}&rdquo;<cite>{src} ({E(when)})</cite></blockquote>'


def page1(ctx):
    people, pulse, rv, J, N = ctx["people"], ctx["pulse"], ctx["reviews"], ctx["judge"], ctx["numbers"]
    items = {it["id"]: it for it in pulse.get("items", [])}
    h = ['<section class="page" id="p1"><div class="wrap"><div class="pnum">Page 1 · The verdict</div>',
         '<h2>How the committee scored it</h2>']
    if pulse.get("banner"):
        h.append(f'<div class="banner">{E(pulse["banner"])}</div>')
    if J["what_changed"]:
        h.append('<h3>What changed this month that shaped this verdict</h3><div class="grid g3">')
        for w in J["what_changed"][:3]:
            it = items.get(w["pulse_id"])
            if not it:
                continue
            h.append(f'<div class="panel change"><p class="headline">{E(it["headline"])}</p><p>{E(_noid(w["line"]))}</p>'
                     f'{_chips([w["pulse_id"]], items)}</div>')
        h.append('</div>')
    lines = {x["persona"]: x["line"] for x in J["persona_lines"]}
    h.append('<h3>Scorecard</h3><p class="note">Each persona scored the copy alone, before the debate. 1 is poor, 7 is excellent.</p>'
             '<div class="scroll"><table><tr><th>Persona</th>' + "".join(f"<th>{E(LABELS[k])}</th>" for k in CRITERIA) +
             '<th>Take the meeting?</th><th>In one line</th></tr>')
    for g, label in (("users", "Users: the people who build and run it"), ("buyers", "Buyers: the people who approve and sign")):
        ids = [x for x in pulse["seat"] if x in rv and people[x].group == g]
        if not ids:
            continue
        h.append(f'<tr class="group"><td colspan="8">{label}</td></tr>')
        for pid in ids:
            r = rv[pid]
            line = lines.get(pid) or lines.get(people[pid].display) or r["first_reaction"]
            h.append(f'<tr><td>{_who(people[pid])}</td>' + "".join(f"<td>{_score(r['scores'][k]['score'])}</td>" for k in CRITERIA) +
                     f'<td><span class="tag t-{r["meeting"]}">{r["meeting"].title()}</span></td><td>{E(line)}</td></tr>')
    h.append('</table></div></div></section>')
    return "".join(h)


def page2(ctx):
    people, pulse, rv, debate = ctx["people"], ctx["pulse"], ctx["reviews"], ctx["debate"]
    items = {it["id"]: it for it in pulse.get("items", [])}
    h = ['<section class="page" id="p2"><div class="wrap"><div class="pnum">Page 2 · The committee talks</div>',
         '<h2>What they said to each other</h2>',
         '<p class="lede">After scoring alone, the committee debated three points. Users speak on the left, buyers on the right. '
         'Every line is synthetic, generated in the voice of a composite persona built from real quotes.</p>']
    if not debate:
        h.append('<p class="note">Only one persona was seated, so there was no debate.</p>')
    for n, pt in enumerate(debate, 1):
        h.append(f'<div class="point"><div class="moderator"><div class="label">Moderator · Point {n}</div>'
                 f'<p class="q">{E(pt["question"])}</p><p class="ctx">{E(pt["context"])}</p>'
                 f'{_chips([pt["pulse_id"]] if pt.get("pulse_id") else [], items)}</div>')
        names = {t["member"]: people[t["persona"]].name for t in pt.get("turns", []) if t.get("member")}
        for t in pt.get("turns", []):
            p = people[t["persona"]]
            t = dict(t, text=_names(t["text"], names))
            side = "right" if p.group == "buyers" else "left"
            moved = ""
            sc = t.get("score_change") or {}
            if sc.get("changed") == "yes" and sc.get("from") is not None and sc["from"] != sc["new_score"]:
                moved = (f'<div class="moved">{E(p.name)} moved <b>{E(LABELS[sc["criterion"]])}</b> from {sc["from"]} to '
                         f'{sc["new_score"]}. {E(sc["why"])}</div>')
            h.append(f'<div class="turn {side}"><div class="bubble">{E(t["text"])}{_chips(t.get("pulse_used"), items)}</div>'
                     f'<div class="speaker"><span class="n">{E(p.name)}</span><span class="r">{E(p.role_label)}</span></div>{moved}</div>')
        h.append('</div>')
    h.append('<div class="recs"><h3>Each persona\'s one recommendation</h3><div class="grid g3">')
    for pid in pulse["seat"]:
        if pid in rv:
            h.append(f'<div class="panel rec">{_who(people[pid])}<p>{E(rv[pid]["key_recommendation"])}</p></div>')
    h.append('</div></div></div></section>')
    return "".join(h)


def page3(ctx):
    people, N, J, pulse = ctx["people"], ctx["numbers"], ctx["judge"], ctx["pulse"]
    rv = ctx["reviews"]
    cl = {x["claim_id"]: x["line"] for x in J["claim_lines"]}
    h = ['<section class="page" id="p3"><div class="wrap"><div class="pnum">Page 3 · Ranking</div>',
         '<h2>Who it works for, and who it loses</h2>',
         '<p class="lede">Users are ranked first because they decide whether the product gets tried. Buyers come second, '
         'but a buyer can veto a claim that would stop the deal.</p>']
    last_group = None
    for n, pid in enumerate(N["ranking"], 1):
        if people[pid].group != last_group:
            last_group = people[pid].group
            h.append(f'<p class="pnum" style="margin:22px 0 4px">{"Users" if last_group == "users" else "Buyers"}</p>')
        m = N["per_persona"][pid]["mean"]
        h.append(f'<div class="rank"><div class="pos">{n}</div><div>{_who(people[pid])}</div>'
                 f'<div class="barcell"><div class="bar"><span style="width:{m / 7 * 100:.0f}%"></span></div></div>'
                 f'<div><b style="color:var(--deep)">{m}</b> / 7 · <span class="tag t-{rv[pid]["meeting"]}">{rv[pid]["meeting"].title()}</span></div></div>')
    h.append('<h3>Claim by claim</h3><div class="scroll"><table><tr><th>Claim</th><th>Users</th><th>Buyers</th><th>Verdict</th><th>Veto</th></tr>')
    fmt = lambda d: ", ".join(f"{v} {k}" for k, v in d.items()) or "none"
    for c in N["claims"]:
        if c["canary"]:
            continue
        veto = ", ".join(people[x].name for x in c["vetoes"]) or ""
        h.append(f'<tr><td><b style="color:var(--deep)">{E(c["text"])}</b><div class="note">{E(_noid(cl.get(c["id"], "")))}</div></td>'
                 f'<td>{E(fmt(c["users"]))}</td><td>{E(fmt(c["buyers"]))}</td>'
                 f'<td><span class="tag t-{c["verdict"]}">{c["verdict"].title()}</span></td><td>{E(veto)}</td></tr>')
    h.append('</table></div>')
    cn = N["canary"]
    canary_txt = (f'Passed. {cn["flagged_weak"]} of {cn["n"]} personas marked a deliberately weak test line as weak or failing.'
                  if cn["pass"] else
                  f'Failed. Only {cn["flagged_weak"]} of {cn["n"]} personas caught a deliberately weak test line. Treat this run as too agreeable.')
    h.append(f'<h3>Honesty checks</h3><p><b style="color:var(--deep)">Canary test:</b> {E(canary_txt)}</p>')
    pr = ctx.get("probe")
    if pr and "shift" in pr:
        verdict = "within tolerance" if abs(pr["shift"]) <= 0.3 else "a sign of flattery, so discount praise in this run"
        h.append(f'<p><b style="color:var(--deep)">Flattery probe:</b> telling {E(people[pr["persona"]].name)} "the team loves this" '
                 f'moved the average score by {pr["shift"]:+}, {verdict}.</p>')
    if J["issues"]:
        h.append('<h3>Problems copy alone cannot fix</h3><ul class="tight">')
        for it in J["issues"]:
            if it["kind"] == "product":
                h.append(f'<li>{E(it["line"])} <span class="note">Owner: {E(it["owner"])}</span></li>')
        h.append('</ul>')
    h.append('</div></section>')
    return "".join(h)


def page4(ctx):
    N, J, pulse, pool, vendors = ctx["numbers"], ctx["judge"], ctx["pulse"], ctx["pool"], ctx["vendors"]
    b = N["blind"]
    claims = {c["id"]: c["text"] for c in pulse["meta"]["claims"]}
    h = ['<section class="page" id="p4"><div class="wrap"><div class="pnum">Page 4 · Competitive view</div>',
         '<h2>Could they tell us apart?</h2>',
         f'<p class="lede">{E(_noid(J["blind_story"]))}</p><div class="grid g3">',
         f'<div class="panel stat"><div class="v">{b["avg_rank"] if b["avg_rank"] is not None else "n/a"}</div><div class="l">Our average rank among {b["vendors"]} vendors (1 is best)</div></div>',
         f'<div class="panel stat"><div class="v">{b["meeting_picks"].get("Nebius", 0)} of {b["n"]}</div><div class="l">Would take the meeting with us first</div></div>',
         f'<div class="panel stat"><div class="v">{b["could_not_tell_apart"]} of {b["n"]}</div><div class="l">Could not tell the vendors apart</div></div></div>',
         '<h3>Who was behind each label</h3><div class="scroll"><table><tr><th>Label</th><th>Vendor</th><th>What they saw</th><th>Stands out (avg)</th><th>Meeting picks</th></tr>']
    for v in sorted(vendors, key=lambda v: v["label"]):
        src = "The copy under review" if v["company"] == "Nebius" else \
            f'<a href="{E(v["url"])}" target="_blank" rel="noopener">{E(v.get("title") or v["url"])}</a> ({E(v.get("date") or "")})'
        h.append(f'<tr><td>{E(v["label"])}</td><td class="who">{E(v["company"])}</td><td>{src}</td>'
                 f'<td>{b["stands_out"].get(v["company"], "")}</td><td>{b["meeting_picks"].get(v["company"], 0)}</td></tr>')
    h.append('</table></div><p class="note">Vendor names were removed from all copy before the committee read it.</p>')
    if J["overlap"]:
        h.append('<h3>Claim by claim: who else says it</h3>')
        for o in J["overlap"]:
            h.append(f'<div class="overlap"><span class="tag t-{o["status"]}">{OVERLAP[o["status"]]}</span>'
                     f'<p class="claim">{E(claims.get(o["claim_id"], o["claim_id"]))}</p><p>{E(_noid(o["explanation"]))}</p>'
                     + "".join(_quote(pool.get(q)) for q in o["quote_ids"][:3]) + '</div>')
    changes = [c for c in pulse.get("competitor_changes", []) if c["change"] and not c["change"].lower().startswith("no material")]
    if changes:
        h.append('<h3>What changed on competitor pages since the Sept 28 library</h3><ul class="tight">')
        for c in changes:
            nl = f' Now reads: &ldquo;{E(c["new_line"])}&rdquo;' if c.get("new_line") else ""
            h.append(f'<li><b style="color:var(--deep)">{E(c["company"])}</b>: {E(c["change"])}{nl} '
                     f'<a class="chip" href="{E(c["url"])}" target="_blank" rel="noopener">live page</a></li>')
        h.append('</ul>')
    if J["patterns"]:
        h.append('<h3>Patterns worth borrowing</h3><p class="note">Structure to learn from, never wording to copy.</p><div class="grid g2">')
        for p in J["patterns"]:
            h.append(f'<div class="panel"><p class="who" style="font-size:17px">{E(p["title"])}</p>'
                     f'{_quote(pool.get(p["quote_id"]))}<p>{E(_noid(p["explanation"]))}</p></div>')
        h.append('</div>')
    h.append('</div></section>')
    return "".join(h)


def page5(ctx):
    people, rws, pool = ctx["people"], ctx["rewrites"], ctx["pool"]
    h = ['<section class="page" id="p5"><div class="wrap"><div class="pnum">Page 5 · Proposed messaging changes</div>',
         '<h2>What to write instead</h2>',
         '<p class="lede">The Nebius marketing writer rewrote the weakest lines using its house rules and playbook. '
         'The committee then compared old and new versions blind. Users decided which won. Any buyer who found the new '
         'line hard to believe could block it.</p>']
    if not rws:
        h.append('<p>No lines needed rewriting.</p>')
    for rw in rws:
        v = rw["vote"]
        u = v["users"]
        h.append(f'<div class="rw"><span class="tag t-{v["status"]}">{STATUS[v["status"]]}</span>'
                 f'<p class="kv" style="margin-top:12px"><b>Before</b></p><p class="before">{E(rw["original"])}</p>'
                 f'<p class="kv"><b>After</b></p><p class="after">{E(rw["proposed"])}</p>'
                 f'<p class="kv"><b>Why:</b> {E(rw["why"])}</p>'
                 f'<p class="kv"><b>Score:</b> {v["before"]} before, {v["after"]} after (committee average, 1 to 7). '
                 f'<b>Users:</b> {u["new"]} preferred the new line, {u["old"]} the original, {u["same"]} no preference.'
                 + (f' <b>Blocked by:</b> {E(", ".join(people[x].name for x in v["vetoes"]))}.' if v["vetoes"] else "") + '</p>')
        if rw["answers"]:
            h.append(f'<p class="kv"><b>Answers:</b> {E(", ".join(rw["answers"]))}</p>')
        if rw.get("pattern_quote_id"):
            h.append('<p class="kv"><b>Borrows the structure of:</b></p>' + _quote(pool.get(rw["pattern_quote_id"])))
        if rw["evidence"]:
            h.append('<p class="kv"><b>Evidence:</b></p><ul class="tight">' + "".join(f"<li>{E(x)}</li>" for x in rw["evidence"]) + '</ul>')
        if rw["placeholders"]:
            h.append('<p class="kv"><b>Fill before publishing:</b></p><ul class="tight">' + "".join(f"<li>{E(x)}</li>" for x in rw["placeholders"]) + '</ul>')
        if rw["issues"]:
            h.append('<p class="kv"><b>Checks that failed:</b></p><ul class="tight">' + "".join(f"<li>{E(x)}</li>" for x in rw["issues"]) + '</ul>')
        h.append('</div>')
    h.append('</div></section>')
    return "".join(h)


def appendix(ctx):
    pulse, meta = ctx["pulse"], ctx["run"]
    h = ['<section class="page" id="method"><div class="wrap"><div class="pnum">Appendix · Method and limits</div>',
         '<h2>How this report was made</h2><ol class="tight">',
         '<li><b>Market Pulse.</b> Tavily searched the sources each persona reads (last 30 days) and competitor newsrooms (last 90 days), '
         'and fetched competitor pages that match this asset type. A reviewer approved the brief before feedback began.</li>',
         '<li><b>Private reviews.</b> Each persona reviewed the copy alone, in a separate model session, using its persona file, '
         'its live items and a blind comparison against competitor copy with names removed.</li>',
         '<li><b>Debate.</b> A moderator picked three points. Personas answered each other, with speakers anonymized.</li>',
         '<li><b>Judge.</b> Code computed every score, rank and veto. A model wrote the summaries and could quote competitors only from verified excerpts.</li>',
         '<li><b>Rewrite.</b> The Nebius marketing writer proposed new lines. Code checked them for copied wording, unsourced numbers and house-rule errors. '
         'The committee re-voted blind.</li></ol>',
         '<h3>What this report cannot tell you</h3><ul class="tight">',
         '<li>The personas are composites built from 334 real quotes by people in each role. They are not real buyers and are not yet calibrated against real buyers.</li>',
         '<li><b>Nebius has no call recordings or customer interview corpus.</b> The strongest possible grounding, what our own buyers say on calls, is not in these personas yet.</li>',
         '<li>Synthetic committees are good at finding objections and unclear claims. They are weak at predicting which message will win in market.</li></ul>',
         '<h3>Live sources used</h3><ul class="tight">']
    for it in pulse.get("items", []):
        when = it["date"] or f"last {it['window_days']} days"
        link = f'<a href="{E(it["url"])}" target="_blank" rel="noopener">{E(it["source"])}</a>' if it.get("url") else E(it["source"])
        h.append(f'<li><b>{E(it["id"])}</b> {E(it["headline"])} {link}, {E(when)}{" (forum sentiment)" if it["tier"] == 3 else ""}</li>')
    if not pulse.get("items"):
        h.append('<li>None.</li>')
    h.append('</ul>' + sources_section(ctx) + '<h3>Run details</h3>'
             f'<p class="note">Run {E(meta["run_id"])} · {E(meta["date"])} · engine {E(meta["engine"])} · '
             f'{meta["model_calls"]} model calls · {meta["tavily_calls"]} Tavily calls ({meta["tavily_cached"]} cached) · '
             f'reported model cost ${meta["cost"]}</p></div></section>')
    return "".join(h)


def sources_section(ctx):
    """Every link the market sweep found, grouped by where it came from."""
    from .pulse import source_rows
    rows = source_rows(ctx["pulse"], ctx["people"])
    if not rows:
        return ""
    order = [("persona reading list", "Where the personas read (last 30 days)"),
             ("market news", "Market news (last 30 days)"),
             ("competitor newsroom", "Competitor newsrooms and blogs (last 90 days)"),
             ("competitor page checked", "Competitor pages checked against the Sept 28 library")]
    h = ['<h3 id="sources">Relevant links and sources</h3>',
         f'<p class="note">All {len(rows)} links the market sweep found for this run, including ones the committee did not use. '
         'Also saved as sources.csv in the run folder, and added to the running sources ledger.</p>']
    for key, title in order:
        grp = [r for r in rows if r["group"] == key]
        if not grp:
            continue
        h.append(f'<p class="kv" style="margin-top:18px"><b>{E(title)}</b> ({len(grp)})</p><ul class="tight">')
        for r in sorted(grp, key=lambda r: (r["used_as"] == "" or not r["used_as"].startswith(("M", "U")), r["source"])):
            meta = [r["source"]]
            if r["date"]:
                meta.append(r["date"])
            if str(r["tier"]) == "3":
                meta.append("forum sentiment")
            if r["used_as"]:
                meta.append(("used as " + r["used_as"]) if r["used_as"][:1] in "MU" else r["used_as"])
            if r["personas"] and key == "persona reading list":
                meta.append("for " + r["personas"])
            h.append(f'<li><a href="{E(r["url"])}" target="_blank" rel="noopener">{E(r["title"] or r["url"])}</a> '
                     f'<span class="note">{E(" · ".join(meta))}</span></li>')
        h.append('</ul>')
    return "".join(h)


def render(ctx):
    pulse, J = ctx["pulse"], ctx["judge"]
    m = pulse["meta"]
    header = (f'<header class="top"><div class="wrap"><div class="brand"><div class="wordmark">nebius<span>.</span> persona committee</div>'
              f'<span class="pill-internal">Internal use only</span></div>'
              f'<div class="kicker">Committee report · {E(m["title"])}</div><h1>{E(J["headline"])}</h1>'
              f'<p class="dek">{E(J["dek"])}</p>'
              f'<div class="meta">{E(ctx["run"]["date"])} · {len(ctx["reviews"])} personas · source: {E(pulse["source"])}</div></div></header>'
              '<nav class="pages"><div class="wrap"><a href="#p1">1 Verdict</a><a href="#p2">2 Dialog</a><a href="#p3">3 Ranking</a>'
              '<a href="#p4">4 Competitive view</a><a href="#p5">5 Proposed changes</a><a href="#method">Method</a><a href="#sources">Sources</a></div></nav>')
    body = header + page1(ctx) + page2(ctx) + page3(ctx) + page4(ctx) + page5(ctx) + appendix(ctx) + \
        '<footer><div class="wrap">Nebius Persona Committee · synthetic feedback for internal message testing · not buyer research</div></footer>'
    tpl = (C.SKILL_DIR / "templates" / "report.html").read_text()
    return tpl.replace("{{TITLE}}", E("Committee Report: " + m["title"])).replace("{{BODY}}", body)
