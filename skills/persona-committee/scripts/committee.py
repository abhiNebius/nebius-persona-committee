#!/usr/bin/env python3
"""Persona Committee CLI.

  committee.py pulse --asset <file|url|->  [--motion M] [--seat P01,P07] [--engine claude|codex] [--pulse-from RUN]
  committee.py edit-pulse <run> [--strike M3,M5] [--add "headline | url"]
  committee.py review <run> [--probe] [--force]
  committee.py run --asset <file|url|->  (no checkpoint; same options as pulse)
  committee.py rewrite <run>   (re-run proposed changes and the re-vote only)
  committee.py render <run>
  committee.py status <run>

A run folder holds every input, prompt output and the final report.html.
"""
import argparse
import json
import re
import shutil
import sys
import urllib.request
from datetime import datetime
from html import unescape
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from committee import config as C  # noqa: E402
from committee import debate, judge, pulse as PU, render, review, rewrite, snap  # noqa: E402
from committee.engine import Engine  # noqa: E402
from committee.library import Library  # noqa: E402
from committee.personas import load as load_personas  # noqa: E402
from committee.tavily import Tavily  # noqa: E402
from committee.util import expand, read_json, slugify, today, write_json  # noqa: E402


def _html_to_text(html):
    html = re.sub(r"(?is)<(script|style|noscript).*?</\1>", " ", html)
    html = re.sub(r"(?i)<br\s*/?>|</(p|div|h[1-6]|li|tr)>", "\n", html)
    return re.sub(r"\n\s*\n+", "\n\n", unescape(re.sub(r"<[^>]+>", " ", html))).strip()


def load_asset(src, tav):
    if src == "-":
        return sys.stdin.read(), "pasted text"
    if re.match(r"https?://", src):
        text = tav.extract([src]).get(src) if tav.available else None
        if not text:
            req = urllib.request.Request(src, headers={"User-Agent": "Mozilla/5.0"})
            text = _html_to_text(urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "ignore"))
        return text, src
    p = expand(src)
    text = p.read_text(encoding="utf-8")
    return (_html_to_text(text) if p.suffix.lower() in (".html", ".htm") else text), p.name


def run_dir_for(cfg, title):
    d = C.path(cfg, "runs_dir") / f"{today()}-{slugify(title, 40)}-{datetime.now().strftime('%H%M%S')}"
    d.mkdir(parents=True, exist_ok=True)
    return d


def resolve_run(cfg, ref):
    p = expand(ref)
    if p.is_dir():
        return p
    p = C.path(cfg, "runs_dir") / ref
    if p.is_dir():
        return p
    raise SystemExit(f"No run folder found for {ref}")


def cmd_pulse(args, cfg, pause=True):
    tav = Tavily(cfg)
    asset_text, label = load_asset(args.asset, tav)
    if len(asset_text.strip()) < 40:
        raise SystemExit("The asset is empty or too short to review.")
    import tempfile
    base = C.path(cfg, "runs_dir")
    base.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="pending-", dir=base))  # unique, so parallel runs never collide
    eng = Engine(cfg, args.engine, tmp / "calls.jsonl")
    people, lib = load_personas(cfg), Library(cfg)
    seat = [x for x in (args.seat or "").split(",") if x] or None
    if args.pulse_from:
        src = resolve_run(cfg, args.pulse_from)
        pulse = read_json(src / "pulse.json")
        pulse["reused_from"] = src.name
    else:
        pulse = PU.build(cfg, eng, tav, lib, people, asset_text, label, args.motion, seat)
    rd = run_dir_for(cfg, pulse["meta"]["title"])
    for f in tmp.iterdir():
        shutil.move(str(f), rd / f.name)
    tmp.rmdir()
    (rd / "asset.txt").write_text(asset_text, encoding="utf-8")
    if re.match(r"https?://", args.asset) and not pulse.get("snapshot"):
        meta = pulse["meta"]
        msgs = [c for c in meta["claims"] if c["id"] != meta["canary_id"]]
        shot = snap.capture(args.asset, {c["id"]: c["text"] for c in msgs}, rd / "asset.jpg",
                            numbers={c["id"]: n for n, c in enumerate(msgs, 1)})
        if shot:
            pulse["snapshot"] = {"image": "asset.jpg", "boxes": shot["boxes"], "width": shot["width"], "height": shot["height"]}
    pulse["approved"] = not pause
    PU.save(rd, pulse, people)
    write_json(rd / "run.json", {"run_id": rd.name, "date": today(), "engine": eng.name, "stage": "pulse",
                                 "tavily": tav.status(), "cost_so_far": eng.total_cost()})
    print(json.dumps({"run": rd.name, "run_dir": str(rd), "pulse_brief": str(rd / "pulse.md"),
                      "seat": pulse["seat"], "items": len(pulse["items"]), "live_check": pulse["live_check"],
                      "banner": pulse.get("banner"), "next": "review" if not pause else "awaiting your review of the pulse"}, indent=2))
    return rd


def cmd_edit(args, cfg):
    rd = resolve_run(cfg, args.run)
    people = load_personas(cfg)
    pulse = PU.edit(read_json(rd / "pulse.json"), (args.strike or "").split(",") if args.strike else [], args.add or [])
    PU.save(rd, pulse, people)
    print(json.dumps({"run": rd.name, "items": [i["id"] for i in pulse["items"]], "approved": True}, indent=2))


def cmd_review(args, cfg, rd=None):
    rd = rd or resolve_run(cfg, args.run)
    pulse = read_json(rd / "pulse.json")
    if not pulse.get("approved") and not args.force:
        raise SystemExit("The Market Pulse has not been approved yet. Run edit-pulse (with no changes to approve as is), or pass --force.")
    runinfo = read_json(rd / "run.json")
    eng = Engine(cfg, runinfo.get("engine"), rd / "calls.jsonl")
    tav_status = runinfo.get("tavily", {})
    people, lib = load_personas(cfg), Library(cfg)
    asset_text = (rd / "asset.txt").read_text(encoding="utf-8")

    if getattr(args, "from_thread", False) and (rd / "reviews.json").exists():
        vendors = read_json(rd / "vendors.json")
        saved = read_json(rd / "reviews.json")
        reviews, errors, probe = saved["reviews"], saved["errors"], saved.get("probe")
    else:
        vendors = review.blind_set(cfg, lib, pulse)
        write_json(rd / "vendors.json", vendors)
        print("Private reviews ...", file=sys.stderr)
        reviews, errors, probe = review.run(eng, people, pulse, asset_text, vendors, probe=args.probe)
        if not reviews:
            raise SystemExit(f"Every persona review failed: {errors}")
        write_json(rd / "reviews.json", {"reviews": reviews, "errors": errors, "probe": probe})
    print("Conversation ...", file=sys.stderr)
    deb = debate.run(eng, people, pulse, reviews)
    write_json(rd / "debate.json", deb)
    print("Judge ...", file=sys.stderr)
    numbers = judge.compute(people, pulse, reviews, vendors, deb)
    pool = judge.quote_pool(cfg, lib, pulse)
    J = judge.write(eng, cfg, people, pulse, reviews, deb, numbers, pool)
    write_json(rd / "numbers.json", numbers)
    write_json(rd / "pool.json", pool)
    write_json(rd / "judge.json", J)
    print("Rewrites and re-vote ...", file=sys.stderr)
    rws = rewrite.run(eng, cfg, lib, people, pulse, reviews, J, pool)
    write_json(rd / "rewrites.json", rws)
    prior = runinfo.get("cost_so_far", 0) or 0
    calls = sum(1 for _ in open(rd / "calls.jsonl")) if (rd / "calls.jsonl").exists() else len(eng.calls)
    runinfo.update({"stage": "done", "model_calls": calls, "cost": round(prior + eng.total_cost(), 2),
                    "review_errors": errors})
    write_json(rd / "run.json", runinfo)
    return cmd_render(None, cfg, rd, tav_status)


def cmd_rewrite(args, cfg):
    """Re-run stage 4 only (rewrites and re-vote) on a finished run, then re-render."""
    rd = resolve_run(cfg, args.run)
    runinfo = read_json(rd / "run.json")
    eng = Engine(cfg, runinfo.get("engine"), rd / "calls.jsonl")
    rws = rewrite.run(eng, cfg, Library(cfg), load_personas(cfg), read_json(rd / "pulse.json"),
                      read_json(rd / "reviews.json")["reviews"], read_json(rd / "judge.json"), read_json(rd / "pool.json"))
    write_json(rd / "rewrites.json", rws)
    runinfo["cost"] = round((runinfo.get("cost") or 0) + eng.total_cost(), 2)
    runinfo["model_calls"] = sum(1 for _ in open(rd / "calls.jsonl"))
    write_json(rd / "run.json", runinfo)
    return cmd_render(None, cfg, rd)


def cmd_render(args, cfg, rd=None, tav_status=None):
    rd = rd or resolve_run(cfg, args.run)
    runinfo = read_json(rd / "run.json")
    tav_status = tav_status or runinfo.get("tavily", {})
    rv = read_json(rd / "reviews.json")
    ctx = {"people": load_personas(cfg), "pulse": read_json(rd / "pulse.json"), "reviews": rv["reviews"],
           "run_dir": rd, "asset_text": (rd / "asset.txt").read_text(encoding="utf-8") if (rd / "asset.txt").exists() else "",
           "probe": rv.get("probe"), "debate": read_json(rd / "debate.json"), "numbers": read_json(rd / "numbers.json"),
           "judge": read_json(rd / "judge.json"), "pool": read_json(rd / "pool.json"),
           "vendors": read_json(rd / "vendors.json"), "rewrites": read_json(rd / "rewrites.json"),
           "run": {"run_id": rd.name, "date": runinfo["date"], "engine": runinfo["engine"],
                   "model_calls": runinfo.get("model_calls", 0), "cost": runinfo.get("cost", 0),
                   "tavily_calls": tav_status.get("calls", 0), "tavily_cached": tav_status.get("cache_hits", 0)}}
    out = rd / "report.html"
    out.write_text(render.render(ctx), encoding="utf-8")
    print(json.dumps({"run": rd.name, "report": str(out), "verdict": ctx["judge"]["verdict"],
                      "canary_pass": ctx["numbers"]["canary"]["pass"],
                      "rewrites": {r["claim_id"]: r["vote"]["status"] for r in ctx["rewrites"]}}, indent=2))
    return out


def cmd_status(args, cfg):
    rd = resolve_run(cfg, args.run)
    print(json.dumps({"run": rd.name, **read_json(rd / "run.json"),
                      "files": sorted(f.name for f in rd.iterdir())}, indent=2))


def main():
    ap = argparse.ArgumentParser(description="Nebius Persona Committee")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("pulse", "run"):
        p = sub.add_parser(name)
        p.add_argument("--asset", required=True)
        p.add_argument("--motion", choices=PU.MOTIONS)
        p.add_argument("--seat", help="Comma-separated persona ids, e.g. P01,P05,P07")
        p.add_argument("--engine", choices=["claude", "codex"])
        p.add_argument("--pulse-from", dest="pulse_from")
        p.add_argument("--probe", action="store_true")
    e = sub.add_parser("edit-pulse")
    e.add_argument("run")
    e.add_argument("--strike")
    e.add_argument("--add", action="append")
    r = sub.add_parser("review")
    r.add_argument("run")
    r.add_argument("--probe", action="store_true")
    r.add_argument("--force", action="store_true")
    r.add_argument("--from-thread", dest="from_thread", action="store_true",
                   help="Keep the saved private reviews; redo the conversation, judge, rewrites and report")
    for name in ("render", "status", "rewrite"):
        sub.add_parser(name).add_argument("run")
    args = ap.parse_args()
    cfg = C.load()
    if args.cmd == "pulse":
        cmd_pulse(args, cfg, pause=cfg["pulse"]["pause_for_review"])
    elif args.cmd == "run":
        rd = cmd_pulse(args, cfg, pause=False)
        args.force = True
        cmd_review(args, cfg, rd)
    elif args.cmd == "edit-pulse":
        cmd_edit(args, cfg)
    elif args.cmd == "review":
        cmd_review(args, cfg)
    elif args.cmd == "rewrite":
        cmd_rewrite(args, cfg)
    elif args.cmd == "render":
        cmd_render(args, cfg)
    elif args.cmd == "status":
        cmd_status(args, cfg)


if __name__ == "__main__":
    main()
