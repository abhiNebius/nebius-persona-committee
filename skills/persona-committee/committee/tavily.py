"""Tavily over plain HTTP: the only API key this skill needs.

Search (news and general, domain-filtered, date-windowed) and extract (live page text).
Every call counts against a per-run budget and is cached for 24 hours.
"""
import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from urllib.parse import urlparse

from . import config as C

API = "https://api.tavily.com/"


class Tavily:
    def __init__(self, cfg):
        t = cfg["tavily"]
        self.key = os.environ.get(t.get("api_key_env", "TAVILY_API_KEY"), "").strip()
        self.budget = t.get("max_calls_per_run", 25)
        self.cache_hours = t.get("cache_hours", 24)
        self.cache_dir = C.path(cfg, "cache_dir") / "tavily"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.used, self.cached, self.errors = 0, 0, []

    @property
    def available(self):
        return bool(self.key)

    def status(self):
        return {"available": self.available, "calls": self.used, "cache_hits": self.cached,
                "budget": self.budget, "errors": self.errors[:5]}

    # -- core ----------------------------------------------------------------
    def _call(self, endpoint, body):
        raw = json.dumps({"ep": endpoint, **body}, sort_keys=True)
        cf = self.cache_dir / (hashlib.sha1(raw.encode()).hexdigest() + ".json")
        if cf.exists() and time.time() - cf.stat().st_mtime < self.cache_hours * 3600:
            self.cached += 1
            return json.loads(cf.read_text())
        if not self.available:
            self.errors.append("No TAVILY_API_KEY set")
            return None
        if self.used >= self.budget:
            self.errors.append(f"Budget of {self.budget} calls reached; skipped: {body.get('query', endpoint)}")
            return None
        self.used += 1
        req = urllib.request.Request(API + endpoint, data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json", "Authorization": "Bearer " + self.key})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                data = json.load(r)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            self.errors.append(f"{endpoint}: {e}")
            return None
        cf.write_text(json.dumps(data))
        return data

    # -- public --------------------------------------------------------------
    def search(self, query, days=30, domains=None, topic="news", max_results=6):
        body = {"query": query[:380], "max_results": max_results, "topic": topic}
        if topic == "news":
            body["days"] = days
        elif days <= 31:
            body["time_range"] = "month"
        else:
            body["start_date"] = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        if domains:
            body["include_domains"] = domains
        data = self._call("search", body) or {}
        if len(data.get("results", [])) < 2 and topic == "news" and days <= 31:
            # thin news index for niche sources: retry as a general search over the same window
            alt = dict(body, topic="general", time_range="month")
            alt.pop("days", None)
            data = self._call("search", alt) or data
        out = []
        for r in data.get("results", []):
            out.append({"url": r.get("url", ""), "title": r.get("title", ""),
                        "date": _date(r.get("published_date")),
                        "domain": urlparse(r.get("url", "")).netloc.replace("www.", ""),
                        "snippet": (r.get("content") or "")[:700], "query": query,
                        "window_days": days})
        return out

    def extract(self, urls):
        urls = [u for u in dict.fromkeys(urls) if u][:20]
        if not urls:
            return {}
        data = self._call("extract", {"urls": urls}) or {}
        return {r.get("url"): r.get("raw_content") or "" for r in data.get("results", [])}


def _date(v):
    if not v:
        return None
    from email.utils import parsedate_to_datetime
    try:
        return parsedate_to_datetime(v).strftime("%Y-%m-%d")
    except (TypeError, ValueError):
        pass
    try:
        return datetime.fromisoformat(v.replace("Z", "")).strftime("%Y-%m-%d")
    except ValueError:
        return v[:16]


def tier(domain, cfg, competitor_domains=()):
    t = cfg["personas_cfg"]["source_tiers"]
    d = domain.lower()
    if any(d.endswith(x) for x in t["tier3"]):
        return 3
    if any(d.endswith(x) for x in t["tier1"]) or any(d.endswith(x) for x in competitor_domains):
        return 1
    return 2
