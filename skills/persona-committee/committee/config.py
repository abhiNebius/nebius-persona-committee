"""Loads the user config, falling back to the bundled example."""
import json
import shutil
from pathlib import Path

from .util import expand

SKILL_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = SKILL_DIR / "config"
USER_CONFIG = expand("~/.config/persona-committee/config.json")


def _merge(base, over):
    out = dict(base)
    for k, v in over.items():
        out[k] = _merge(base[k], v) if isinstance(v, dict) and isinstance(base.get(k), dict) else v
    return out


def load():
    cfg = json.loads((CONFIG_DIR / "config.example.json").read_text())
    if USER_CONFIG.exists():
        cfg = _merge(cfg, json.loads(USER_CONFIG.read_text()))
    cfg["personas_cfg"] = json.loads((CONFIG_DIR / "personas.json").read_text())
    cfg["competitors_cfg"] = json.loads((CONFIG_DIR / "competitors.json").read_text())
    cfg["skill_dir"] = str(SKILL_DIR)
    return cfg


def path(cfg, key):
    return expand(cfg["paths"][key])


def find_bin(cfg, engine):
    name = cfg.get(f"{engine}_bin", engine)
    found = shutil.which(name) or shutil.which(engine)
    if found:
        return found
    if engine == "codex":
        for p in ("/Applications/ChatGPT.app/Contents/Resources/codex", "/Applications/Codex.app/Contents/Resources/codex"):
            if Path(p).exists():
                return p
    for p in (expand("~/.local/bin/" + engine),):
        if p.exists():
            return str(p)
    raise SystemExit(f"Could not find the {engine} command. Install it or set {engine}_bin in {USER_CONFIG}.")


def reference(name):
    return (SKILL_DIR / "references" / name).read_text()
