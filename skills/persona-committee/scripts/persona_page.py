#!/usr/bin/env python3
"""Builds the Confluence page that lists every persona, from the persona library.

  persona_page.py > personas.storage.html     Confluence storage format (XHTML)

Each persona gets an anchor (P01 ... P11) so reports can link straight to it.
Internal evidence references ("[internal: ...]") are stripped; the page links back to nothing private.
"""
import re
import sys
from html import escape as E
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from committee import config as C  # noqa: E402
from committee.personas import load  # noqa: E402

LINK = re.compile(r"\[([^\]]+)\]\((https?://[^)]+)\)")


def _text(md):
    md = re.sub(r"\s*\(?\[internal:[^\]]*\]\)?", "", md)
    out, pos = [], 0
    for m in LINK.finditer(md):
        out.append(E(md[pos:m.start()]))
        out.append(f'<a href="{E(m.group(2))}">{E(m.group(1))}</a>')
        pos = m.end()
    out.append(E(md[pos:]))
    s = "".join(out)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    return s.replace("*", "")


def _section(body, name):
    m = re.search(r"^## " + re.escape(name) + r".*?\n(.*?)(?=^## |\Z)", body, re.S | re.M)
    return m.group(1) if m else ""


def _glance(body):
    rows = {}
    for line in _section(body, "At a Glance").splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) == 2 and cells[0].strip("*") not in ("Field", "---"):
            rows[cells[0].strip("*").strip()] = cells[1]
    return rows


def _pains(body, n=3):
    return re.findall(r"^\*\*(?:\d+\.\s*)?(.+?)\*\*", _section(body, "What Keeps Them Up"), re.M)[:n]


def _trust(body, n=4):
    sec = _section(body, "How They Read Vendor Content")
    m = re.search(r"\*\*What earns trust\.?\*\*(.*?)(?=\n\*\*|\Z)", sec, re.S)
    if not m:
        return []
    items = re.findall(r"^- (.+)$", m.group(1), re.M)
    if not items:  # written as a paragraph: one item per sentence
        items = [x for x in re.split(r"(?<=[.!?])\s+", m.group(1).strip()) if len(x) > 12]
    return [re.split(r"(?<=[.!?])\s", x, maxsplit=1)[0] for x in items][:n]


def _roster(lib):
    idx = next(iter(lib.glob("00 *.md")), None)
    out = {}
    if not idx:
        return out
    for line in idx.read_text().splitlines():
        line = line.replace("\\|", "/")  # wikilink aliases escape the pipe inside table cells
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 6 and re.fullmatch(r"P\d\d", cells[0]):
            out[cells[0]] = {"role_in_deal": cells[2], "veto": cells[3], "meet": cells[4], "want": cells[5]}
    return out


def build(cfg):
    people = load(cfg)
    lib = C.path(cfg, "persona_library")
    roster = _roster(lib)
    files = {f.name[:3]: f.read_text(encoding="utf-8") for f in lib.glob("P[0-9][0-9] *.md")}
    h = ['<ac:structured-macro ac:name="info"><ac:rich-text-body><p><strong>Internal.</strong> Eleven synthetic buyer personas used by '
         'the Persona Committee to pressure-test Nebius messaging. Each is a composite built from 25 to 45 real, linked quotes by people '
         'in that role (334 in total), public research and Nebius deal records. They are not real people and are not yet calibrated '
         'against real buyers. Nebius has no call recordings or customer interview corpus yet.</p></ac:rich-text-body></ac:structured-macro>',
         '<h2>Who is on the committee</h2>',
         '<p><strong>Users</strong> build and run the product and vote first on whether messaging resonates. '
         '<strong>Buyers</strong> approve and sign, and can veto a claim that would stop the deal.</p>',
         '<table><tbody><tr><th>#</th><th>Persona</th><th>Group</th><th>Role in the deal</th><th>The one thing they want</th></tr>']
    for pid, p in people.items():
        r = roster.get(pid, {})
        h.append(f'<tr><td>{pid}</td><td><ac:link ac:anchor="{pid}"><ac:plain-text-link-body><![CDATA[{p.display}]]>'
                 f'</ac:plain-text-link-body></ac:link></td><td>{"User" if p.group == "users" else "Buyer"}</td>'
                 f'<td>{E(r.get("role_in_deal", p.buying_role))}</td><td>{E(r.get("want", ""))}</td></tr>')
    h.append('</tbody></table>')
    h.append('<h2>Who to seat for each kind of deal</h2><ul>'
             '<li><strong>Token Factory sprint</strong> (inference API, closes in days): Founder-CTO Farah, Inference Engineer Ingrid, '
             'AI Engineer Alan, Platform Head Priya.</li>'
             '<li><strong>Capacity deal</strong> (GPU clusters, often prepaid): Research Founder Randy, GPU Engineer Gabe, CFO Clara, '
             'Compute Head Campbell.</li>'
             '<li><strong>Enterprise relay</strong> (months, procurement from day one): Platform Head Priya, CFO Clara, CISO Cecil, '
             'Procurement Head Paula, AI Executive Eva.</li></ul>')
    for group, title in (("users", "Users"), ("buyers", "Buyers")):
        h.append(f'<h2>{title}</h2>')
        for pid, p in people.items():
            if p.group != group:
                continue
            body = files.get(pid, "")
            g = _glance(body)
            r = roster.get(pid, {})
            h.append(f'<ac:structured-macro ac:name="anchor"><ac:parameter ac:name="">{pid}</ac:parameter></ac:structured-macro>')
            h.append(f'<h3>{E(p.display)}</h3><p><em>{_text(p.tagline)}</em></p><table><tbody>')
            for label, key in (("Titles they go by", "Titles this persona goes by"), ("Role in the deal and veto", "Buying role and veto"),
                               ("Joins the deal", "Enters the deal at"), ("Measured on", "Measured on (KPIs)"),
                               ("Where you find them", "Where you find them")):
                val = g.get(key) or next((v for k, v in g.items() if k.lower().startswith(key.lower()[:12])), "")
                if val:
                    val = re.sub(r"^([a-z]+)_([a-z_]+)", lambda m: (m.group(1) + " " + m.group(2).replace("_", " ")).capitalize(), val)
                    h.append(f'<tr><th>{label}</th><td>{_text(val)}</td></tr>')
            h.append('</tbody></table>')
            pains = _pains(body)
            if pains:
                h.append('<p><strong>What keeps them up at night</strong></p><ul>' + "".join(f"<li>{_text(x)}</li>" for x in pains) + '</ul>')
            trust = _trust(body)
            if trust:
                h.append('<p><strong>What earns their trust</strong></p><ul>' + "".join(f"<li>{_text(x)}</li>" for x in trust) + '</ul>')
            if r.get("want"):
                h.append(f'<p><strong>How to message them:</strong> lead with {E(r["want"][0].lower() + r["want"][1:])}, '
                         f'and back it with the proof above. Where you meet them: {E(r.get("meet", ""))}.</p>')
    h.append('<h2>How the personas are used</h2><p>The Persona Committee skill (Claude Code and Codex) seats the right personas for an asset, '
             'checks the live market and Nebius&rsquo;s own published record, has each persona score every message out of 7, runs a '
             'committee conversation, and proposes rewrites backed by Nebius-published proof. Personas are refreshed through an '
             'approval-gated weekly review.</p>')
    return "\n".join(h)


if __name__ == "__main__":
    print(build(C.load()))
