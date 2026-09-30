"""The Nebius fact sweep: what Nebius itself has published, checked before the committee meets.

Sources, newest first:
  1. Local corpus of nebius.com blog posts and press releases (Markdown with dated frontmatter).
  2. Tavily search of nebius.com for the last 30 days (catches anything newer, and works without the corpus).

Output, per message in the asset: supporting facts (verbatim sentences, dated, linked), plus
published proof the asset does not use. The moderator, judge and writer use it so the report never
states something false about Nebius. The personas never see it: they react only to the page.
"""
import math
import re
from collections import Counter
from datetime import datetime

from .util import arr, expand, norm, obj, s, untrusted

STOP = set("""a an the and or of to in on for with by at from as is are was were be been it its this that these those
we our you your they their them he she his her not no but if then than so such can will would should could into over
under about more most less very just also all any each other new now use using used via per vs how what when where which
who why nebius ai""".split())


def _tokens(text):
    return [w for w in re.findall(r"[a-z0-9][a-z0-9.+-]*", text.lower()) if w not in STOP and len(w) > 1]


def _frontmatter(text):
    m = re.match(r"---\n(.*?)\n---\n", text, re.S)
    meta = {}
    if m:
        for line in m.group(1).splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                meta[k.strip()] = v.strip().strip('"')
        text = text[m.end():]
    return meta, text


class Corpus:
    def __init__(self, cfg):
        self.passages = []
        for folder in cfg["paths"].get("nebius_corpus", []):
            root = expand(folder)
            if not root.exists():
                continue
            for f in root.rglob("*.md"):
                meta, body = _frontmatter(f.read_text(encoding="utf-8", errors="ignore"))
                kind = "press release" if "Press release" in meta.get("tags", "") or "Newsroom" in str(f) else "blog"
                for chunk in _chunks(body):
                    self.passages.append({"title": meta.get("title", f.stem), "url": meta.get("source_url", ""),
                                          "date": meta.get("date", "")[:10], "kind": kind, "text": chunk})
        # the messaging frameworks carry approved proof points (customer stories, stats) too
        for f in cfg["paths"].get("claims_sources", []):
            fp = expand(f)
            if fp.exists():
                meta, body = _frontmatter(fp.read_text(encoding="utf-8", errors="ignore"))
                for chunk in _chunks(body):
                    self.passages.append({"title": fp.stem.replace("REFERENCE ", "").replace("CURRENT ", ""), "url": "",
                                          "date": "", "kind": "messaging framework", "text": chunk})
        self._index()

    def _index(self):
        self.tf = [Counter(_tokens(p["title"] + " " + p["text"])) for p in self.passages]
        self.df = Counter(t for tf in self.tf for t in tf)
        self.n = len(self.passages)
        self.avgdl = (sum(sum(tf.values()) for tf in self.tf) / self.n) if self.n else 1

    def search(self, query, k=6, today=None):
        if not self.n:
            return []
        q = set(_tokens(query))
        today = today or datetime.now()
        scored = []
        for i, tf in enumerate(self.tf):
            dl = sum(tf.values()) or 1
            sc = 0.0
            for t in q:
                if t in tf:
                    idf = math.log(1 + (self.n - self.df[t] + 0.5) / (self.df[t] + 0.5))
                    sc += idf * tf[t] * 2.2 / (tf[t] + 1.2 * (0.25 + 0.75 * dl / self.avgdl))
            if sc <= 0:
                continue
            d = self.passages[i]["date"]
            try:
                age = (today - datetime.strptime(d, "%Y-%m-%d")).days
                sc *= 1.6 if age <= 90 else 1.3 if age <= 180 else 1.0 if age <= 365 else 0.7
            except ValueError:
                pass
            scored.append((sc, i))
        return [self.passages[i] for _, i in sorted(scored, reverse=True)[:k]]


def _chunks(body, target=110):
    paras = [p.strip() for p in re.split(r"\n\s*\n", body) if len(p.strip()) > 60 and not p.strip().startswith(("![", "|---"))]
    out, buf = [], ""
    for p in paras:
        buf = (buf + "\n\n" + p).strip()
        if len(buf.split()) >= target:
            out.append(buf)
            buf = ""
    if buf:
        out.append(buf)
    return out


FACTS_SCHEMA = obj(
    supports=arr(obj(claim_id=s(), passage_id=s(),
                     fact=s("One plain sentence stating the published fact that supports or sharpens this message"),
                     quote=s("The exact sentence from the passage that proves it, copied character for character"))),
    unused=arr(obj(passage_id=s(), fact=s("One plain sentence"),
                   quote=s("The exact sentence from the passage, copied character for character"),
                   pillar=s(enum=["build_faster", "scale_with_confidence", "own_your_intelligence", "none"]),
                   why=s("One sentence: why this proof would make the asset stronger"))),
    standing_facts=arr(obj(passage_id=s(), fact=s("A current, checkable fact about Nebius a reviewer must not contradict"),
                           quote=s("The exact sentence from the passage"))),
)


def sweep(cfg, engine, tav, meta):
    corpus = Corpus(cfg)
    pool, seen = {}, set()

    def add(p):
        key = (p["url"], p["text"][:80])
        if key in seen:
            return
        seen.add(key)
        pid = f"N{len(pool) + 1}"
        pool[pid] = dict(p, id=pid)

    for c in meta["claims"]:
        if c["id"] == meta["canary_id"]:
            continue
        for p in corpus.search(c["text"] + " " + c.get("label", ""), k=4):
            add(p)
    # standing facts buyers often get wrong: third-party ratings, capacity, customers, launches
    for q in ("SemiAnalysis ClusterMAX rating Platinum", "MLPerf results record", "data center capacity power owned",
              "customer story results", "Token Factory launch", "security compliance certification SOC 2 ISO"):
        for p in corpus.search(q, k=2):
            add(p)
    live = []
    if tav.available:
        for r in tav.search("Nebius announcement", days=cfg["tavily"]["news_days"], domains=[cfg["paths"].get("nebius_domain", "nebius.com")],
                            topic="general", max_results=6):
            live.append(r)
            add({"title": r["title"], "url": r["url"], "date": r["date"] or "", "kind": "nebius.com (live)", "text": r["snippet"]})
    if not pool:
        return {"pool": {}, "supports": [], "unused": [], "standing": [], "corpus_size": corpus.n, "live": len(live)}

    claims = "\n".join(f"{c['id']} [{c.get('label', '')}; pillar {c.get('pillar', 'none')}]: {c['text']}"
                       for c in meta["claims"] if c["id"] != meta["canary_id"])
    passages = "\n\n".join(f"{pid} | {p['kind']} | {p['date'] or 'recent'} | {p['title']}\n" + untrusted(p["url"], p["text"][:1200])
                           for pid, p in pool.items())
    system = ("You are a Nebius product marketing fact-checker. From the passages Nebius itself has published, pick the facts "
              "that support or sharpen each message in the asset, the strongest published proof the asset does not use, and "
              "standing facts about Nebius that any reviewer must not contradict (ratings, certifications, capacity, named "
              "customers, launches). Prefer the newest passage when two conflict. Every quote must be copied exactly from its "
              "passage. Value pillars: build_faster (dev-first, frontier-ready), scale_with_confidence (predictable capacity, "
              "performance, economics), own_your_intelligence (open-model choice, full-stack control). No em-dashes.")
    out = engine.run(system, f"ASSET MESSAGES\n{claims}\n\nNEBIUS-PUBLISHED PASSAGES\n{passages}", FACTS_SCHEMA,
                     tier="deep", label="nebius:facts")

    def ok(x):
        p = pool.get(x["passage_id"])
        return bool(p) and norm(x["quote"]).strip(" .\"'")[:120] in norm(p["text"])

    return {"pool": pool, "corpus_size": corpus.n, "live": len(live),
            "supports": [x for x in out["supports"] if ok(x)],
            "unused": [x for x in out["unused"] if ok(x)][:6],
            "standing": [x for x in out["standing_facts"] if ok(x)][:8]}


def brief(facts):
    """Short text block of verified Nebius facts for moderator, grader, judge and writer prompts."""
    rows = []
    for x in facts.get("standing", []) + facts.get("unused", []) + facts.get("supports", []):
        p = facts["pool"].get(x["passage_id"], {})
        rows.append(f"{x['passage_id']} ({p.get('date') or 'recent'}, {p.get('kind', '')}): {x['fact']}")
    return "\n".join(dict.fromkeys(rows)) or "none found"
