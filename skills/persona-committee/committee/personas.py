"""Parses the persona library (Obsidian markdown) into structured personas.

The persona files are the source of truth. This module only reads them.
"""
import re
from dataclasses import dataclass, field

from . import config as C


@dataclass
class Persona:
    pid: str
    display: str          # "CFO Clara"
    name: str             # "Clara"
    role_label: str       # "CFO"
    role: str             # frontmatter role, long form
    group: str            # "users" | "buyers"
    buying_role: str
    motions: list
    agent_block: str
    activation: str
    concerns: str
    reading: str
    voice: str
    tagline: str
    sources: list = field(default_factory=list)

    def card(self):
        return {"id": self.pid, "display": self.display, "name": self.name, "role_label": self.role_label,
                "role": self.role, "group": self.group, "buying_role": self.buying_role}


def _frontmatter(text):
    m = re.match(r"---\n(.*?)\n---\n", text, re.S)
    fm = {}
    if not m:
        return fm, text
    for line in m.group(1).splitlines():
        if ":" not in line or line.startswith(" "):
            continue
        k, v = line.split(":", 1)
        v = v.strip()
        if v.startswith("[") and v.endswith("]"):
            v = [x.strip().strip('"') for x in v[1:-1].split(",") if x.strip()]
        else:
            v = v.strip('"')
        fm[k.strip()] = v
    return fm, text[m.end():]


def _sections(body):
    out, cur, buf = {}, "_intro", []
    for line in body.splitlines():
        if line.startswith("## "):
            out[cur] = "\n".join(buf).strip()
            cur, buf = line[3:].strip(), []
        else:
            buf.append(line)
    out[cur] = "\n".join(buf).strip()
    return out


def _find(sections, prefix):
    for k, v in sections.items():
        if k.lower().startswith(prefix.lower()):
            return v
    return ""


def _clip(text, limit):
    return text if len(text) <= limit else text[:limit].rsplit("\n", 1)[0] + "\n[...]"


def load(cfg):
    pcfg = cfg["personas_cfg"]
    group_of = {pid: g for g, ids in pcfg["groups"].items() for pid in ids}
    lib = C.path(cfg, "persona_library")
    people = {}
    for f in sorted(lib.glob("P[0-9][0-9] *.md")):
        text = f.read_text(encoding="utf-8")
        fm, body = _frontmatter(text)
        pid = fm.get("persona_id") or f.name[:3]
        h1 = re.search(r"^# (.+)$", body, re.M)
        display = (h1.group(1).strip() if h1 else fm.get("name", f.stem[4:]))
        tag = re.search(r"^\*(.+)\*$", body, re.M)
        sec = _sections(body)
        agent_sec = _find(sec, "Agent Instructions")
        fence = re.search(r"```[a-z]*\n(.*?)```", agent_sec, re.S)
        agent_block = fence.group(1).strip() if fence else agent_sec
        activation = agent_sec[fence.end():].strip() if fence else ""
        parts = display.split()
        people[pid] = Persona(
            pid=pid, display=display, name=parts[-1], role_label=" ".join(parts[:-1]),
            role=fm.get("role", ""), group=group_of.get(pid, "users"),
            buying_role=fm.get("buying_role", ""),
            motions=fm.get("motions", []) if isinstance(fm.get("motions"), list) else [],
            agent_block=agent_block, activation=_clip(activation, 2500),
            concerns=_clip(_find(sec, "What Keeps Them Up"), 5000),
            reading=_clip(_find(sec, "How They Read Vendor Content"), 4000),
            voice=_clip(_find(sec, "How They Talk"), 5000),
            tagline=tag.group(1).strip() if tag else "",
            sources=pcfg["reading_sources"].get(pid, []),
        )
    if len(people) < 11:
        raise SystemExit(f"Expected 11 persona files in {lib}, found {len(people)}.")
    return people


def seat(people, cfg, motion, asset_type=None, override=None):
    """Pick the committee for this asset. Users first, then buyers."""
    pcfg = cfg["personas_cfg"]
    if override:
        ids = [x.strip().upper() for x in override]
    else:
        ids = list(pcfg["motions"].get(motion) or pcfg["motions"]["brand"])
        for extra in pcfg.get("asset_type_adds", {}).get(str(asset_type or ""), []):
            if extra not in ids:
                ids.append(extra)
    ids = [x for x in ids if x in people][: cfg["committee"]["max_seats"]]
    order = pcfg["groups"]["users"] + pcfg["groups"]["buyers"]
    return sorted(ids, key=order.index)
