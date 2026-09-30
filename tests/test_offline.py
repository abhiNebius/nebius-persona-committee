"""Offline checks: no model calls, no Tavily calls. Run: python3 tests/test_offline.py

Needs the persona library and the Marketing Asset Library at the configured paths.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "skills" / "persona-committee"))

from committee import config, library, personas, render, rewrite  # noqa: E402
from committee.util import clean  # noqa: E402

EM, EN = chr(0x2014), chr(0x2013)


def test_personas(cfg):
    people = personas.load(cfg)
    assert len(people) == 11, len(people)
    for p in people.values():
        assert p.agent_block and p.name and p.role_label, p.pid
    assert [p.group for p in people.values()].count("users") == 6
    seat = personas.seat(people, cfg, "enterprise_relay", "11")
    assert seat == ["P03", "P07", "P08", "P09", "P10"], seat
    return people


def test_library(cfg):
    lib = library.Library(cfg)
    assert len(lib.entries) >= 300, len(lib.entries)
    e = lib.best("CoreWeave", "01")
    assert e and e.url.startswith("https://"), e
    assert lib.is_verbatim(e.lines[0])
    assert not lib.is_verbatim("Nebius is the only cloud that never fails, guaranteed forever")
    name, text = lib.playbook("11")
    assert "Pricing" in name and text


def test_text_rules():
    assert EM not in clean(f"one {EM} two") and EN not in clean(f"20{EN}40")
    assert render._names("Member A is right, and Members A and B agree", {"A": "Farah", "B": "Clara"}) == \
        "Farah is right, and Farah and Clara agree"
    assert render._noid("Crusoe's support line (Q24) cites a score") == "Crusoe's support line cites a score"


def test_rewrite_checks(cfg):
    lib = library.Library(cfg)
    copied = lib.best("CoreWeave", "01").lines[1]
    rw = {"proposed": copied}
    issues, _ = rewrite.check(cfg, lib, rw, "old line", "", "01")
    assert any("competitor" in x for x in issues), issues
    rw = {"proposed": "Save 73% with [a] [b] [c] [d]"}
    issues, _ = rewrite.check(cfg, lib, rw, "old line", "", "01")
    assert any("Numbers" in x for x in issues) and any("placeholders" in x for x in issues), issues


if __name__ == "__main__":
    cfg = config.load()
    test_personas(cfg)
    test_library(cfg)
    test_text_rules()
    test_rewrite_checks(cfg)
    print("all offline checks passed")
