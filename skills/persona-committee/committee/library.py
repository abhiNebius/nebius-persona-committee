"""Reads the Marketing Asset Library: competitor excerpts (verbatim) and asset-type playbooks."""
import re
from dataclasses import dataclass, field

from . import config as C
from .util import norm


@dataclass
class Entry:
    eid: str
    company: str
    title: str
    url: str
    date: str
    lines: list
    proof: str = ""
    voice: str = ""
    asset_types: list = field(default_factory=list)

    def text(self, limit=10):
        return "\n".join("> " + x for x in self.lines[:limit])


class Library:
    def __init__(self, cfg):
        self.cfg = cfg
        self.root = C.path(cfg, "competitor_library")
        ccfg = cfg["competitors_cfg"]
        self.companies = ccfg["companies"]
        self.kw = ccfg["asset_type_keywords"]
        self.entries = []
        self._parse()

    # -- parsing -------------------------------------------------------------
    def canonical(self, name):
        n = name.lower()
        for canon, meta in self.companies.items():
            for a in meta["aliases"] + [canon]:
                if re.search(r"(^|\W)" + re.escape(a.lower()) + r"(\W|$)", n):
                    return canon
        return None

    def _types(self, title):
        t = title.lower()
        return [k for k, kws in self.kw.items() if any(re.search(r"(^|\W)" + re.escape(w) + r"(\W|$)", t) for w in kws)]

    def _parse(self):
        folder = self.root / "Excerpts by Competitor"
        for f in sorted(folder.glob("*.md")):
            short = re.sub(r"^Excerpts - ", "", f.stem)[:24]
            h2_company, cur, field_, n_entries = None, None, None, 0
            for line in f.read_text(encoding="utf-8").splitlines():
                if line.startswith("## "):
                    h2_company = self.canonical(re.sub(r"\(tier:.*?\)", "", line[3:]).strip())
                    cur = None
                    continue
                m = re.match(r"### Entry: (\d+)\s*([^|]*)\|\s*(.+)", line)
                if m:
                    # The entry number is the asset-type id (1 homepage, 11 pricing, 14 paid ads ...).
                    atype = f"{int(m.group(1)):02d}"
                    rest = [x.strip() for x in m.group(3).split("|")]
                    title = rest[-1]
                    company = (self.canonical(rest[0]) if len(rest) > 1 else None) or self.canonical(title) or h2_company
                    types = [atype] + [t for t in self._types(title) if t != atype]
                    n_entries += 1
                    cur = Entry(eid=f"{short}#{n_entries}", company=company or "Unknown", title=title,
                                url="", date="", lines=[], asset_types=types)
                    self.entries.append(cur)
                    field_ = None
                    continue
                if cur is None:
                    continue
                if line.startswith("- URL:"):
                    cur.url = line.split(":", 1)[1].strip()
                elif line.startswith("- Date:"):
                    cur.date = line.split(":", 1)[1].strip()
                elif line.startswith("- Verbatim excerpts"):
                    field_ = "v"
                elif line.startswith("- Proof devices:"):
                    cur.proof, field_ = line.split(":", 1)[1].strip(), None
                elif line.startswith("- Voice notes:"):
                    cur.voice, field_ = line.split(":", 1)[1].strip(), None
                elif line.startswith("- "):
                    field_ = None
                elif field_ == "v" and line.strip().startswith(">"):
                    q = line.strip()[1:].strip()
                    if q and not q.startswith("CTA:"):
                        cur.lines.append(q)

    # -- queries -------------------------------------------------------------
    def for_company(self, company):
        return [e for e in self.entries if e.company == company and e.lines]

    def best(self, company, asset_type):
        es = self.for_company(company)
        if not es:
            return None
        for pref in (str(asset_type), "01", "02"):
            hit = [e for e in es if pref in e.asset_types]
            if hit:
                return max(hit, key=lambda e: len(e.lines))
        return max(es, key=lambda e: len(e.lines))

    def corpus(self, companies=None):
        return [(e, ln) for e in self.entries if (not companies or e.company in companies) for ln in e.lines]

    def is_verbatim(self, quote, extra_texts=()):
        """True if the quote appears in the library or in live-fetched text. Used to drop paraphrases."""
        q = norm(quote).strip(" .\"'")
        if len(q) < 12:
            return False
        for _, ln in self.corpus():
            if q in norm(ln):
                return True
        return any(q in norm(t) for t in extra_texts)

    def playbook(self, asset_type, sections=("3.", "4.", "5.", "10.")):
        folder = self.root / "Asset Type Playbooks"
        f = next(iter(sorted(folder.glob(f"Playbook {int(asset_type):02d} - *.md"))), None) if str(asset_type).isdigit() else None
        if not f:
            f = next(iter(sorted(folder.glob("Playbook 02 - *.md"))), None)
        if not f:
            return "", ""
        text, keep, on = f.read_text(encoding="utf-8"), [], False
        for line in text.splitlines():
            if line.startswith("## "):
                on = any(line[3:].startswith(sn) for sn in sections)
            if on:
                keep.append(line)
        return f.stem, "\n".join(keep)
