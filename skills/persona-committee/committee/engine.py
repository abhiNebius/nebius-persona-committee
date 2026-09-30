"""Runs one isolated model call on Claude Code or Codex and returns schema-shaped JSON.

Every call is its own process, so personas never share a context. Persona calls run in
lean mode: no tools, no user settings, no MCP servers, a purpose-built system prompt.
Both hosts use their own login, so no model API key is needed.
"""
import json
import re
import subprocess
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import config as C
from .util import clean


class EngineError(RuntimeError):
    pass


class Engine:
    def __init__(self, cfg, engine=None, log_path=None):
        self.cfg = cfg
        self.name = engine or cfg.get("engine", "claude")
        self.bin = C.find_bin(cfg, self.name)
        self.models = cfg["models"].get(self.name, {})
        self.log_path = Path(log_path) if log_path else None
        self.calls = []
        self._lock = threading.Lock()

    # -- public --------------------------------------------------------------
    def run(self, system, prompt, schema, tier="fast", label="call", retries=1):
        last = None
        for attempt in range(retries + 1):
            t0 = time.time()
            try:
                out, cost = (self._claude if self.name == "claude" else self._codex)(system, prompt, schema, tier)
                self._log(label, tier, time.time() - t0, cost, ok=True)
                return clean(out)
            except EngineError as e:
                last = e
                self._log(label, tier, time.time() - t0, 0, ok=False, err=str(e)[:300])
        raise EngineError(f"{label} failed after {retries + 1} attempts: {last}")

    def map(self, jobs):
        """jobs: list of (key, kwargs for run). Returns {key: result or Exception}."""
        results = {}
        with ThreadPoolExecutor(max_workers=self.cfg.get("parallel_calls", 6)) as ex:
            futs = {ex.submit(self.run, **kw): key for key, kw in jobs}
            for f in futs:
                key = futs[f]
                try:
                    results[key] = f.result()
                except Exception as e:  # keep the run alive; callers decide what a failure means
                    results[key] = e
        return results

    def total_cost(self):
        return round(sum(c.get("cost", 0) or 0 for c in self.calls), 4)

    # -- hosts ---------------------------------------------------------------
    def _claude(self, system, prompt, schema, tier):
        cmd = [self.bin, "-p", "--tools", "", "--setting-sources", "", "--strict-mcp-config",
               "--no-session-persistence", "--output-format", "json",
               "--system-prompt", system, "--json-schema", json.dumps(schema)]
        model = self.models.get(tier)
        if model:
            cmd += ["--model", model]
        p = subprocess.run(cmd, input=prompt, capture_output=True, text=True, timeout=900)
        try:
            d = json.loads(p.stdout)
        except json.JSONDecodeError:
            raise EngineError(f"claude returned non-JSON (exit {p.returncode}): {p.stdout[:200]} {p.stderr[:200]}")
        if d.get("is_error"):
            raise EngineError(f"claude error: {str(d.get('result'))[:300]}")
        out = d.get("structured_output")
        if out is None:
            out = _extract_json(d.get("result", ""))
        return out, d.get("total_cost_usd", 0)

    def _codex(self, system, prompt, schema, tier):
        with tempfile.TemporaryDirectory() as td:
            sf, of = Path(td) / "schema.json", Path(td) / "out.json"
            sf.write_text(json.dumps(schema))
            cmd = [self.bin, "exec", "--skip-git-repo-check", "--ephemeral", "-s", "read-only",
                   "-C", td, "--output-schema", str(sf), "-o", str(of)]
            model = self.models.get(tier)
            if model:
                cmd += ["-m", model]
            cmd.append("-")
            full = f"{system}\n\n=====\n\n{prompt}"
            p = subprocess.run(cmd, input=full, capture_output=True, text=True, timeout=900)
            if not of.exists():
                raise EngineError(f"codex produced no output (exit {p.returncode}): {p.stderr[-300:]}")
            return _extract_json(of.read_text()), 0

    def _log(self, label, tier, secs, cost, ok, err=None):
        rec = {"label": label, "tier": tier, "seconds": round(secs, 1), "cost": cost, "ok": ok}
        if err:
            rec["error"] = err
        with self._lock:
            self.calls.append(rec)
            if self.log_path:
                with open(self.log_path, "a") as f:
                    f.write(json.dumps(rec) + "\n")


def _extract_json(text):
    if isinstance(text, (dict, list)):
        return text
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        m = re.search(r"\{.*\}", text or "", re.S)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                pass
    raise EngineError(f"could not parse JSON from model output: {str(text)[:200]}")
