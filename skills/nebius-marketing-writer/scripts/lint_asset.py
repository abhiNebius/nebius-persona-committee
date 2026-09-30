#!/usr/bin/env python3
"""Lint a Nebius marketing draft against the house rules.

Usage:
    python3 lint_asset.py <draft.md> [--type NN] [--final]

--type NN   asset-type number from the playbook map (01..19). Enables
            type-specific checks (headline length, ad limits, required sections).
--final     treat unsourced metrics and open placeholders as errors.
--ignore-quotes  skip text inside double quotes (for internal pieces that quote
            competitors, such as analyses or training material).

Exit code 1 if any ERROR is found. Prints a report grouped by severity.
"""
import argparse
import re
import sys

EM_DASH = chr(0x2014)
EN_DASH = chr(0x2013)

BANNED_PHRASES = [
    "purpose-built", "purpose built", "at scale", "pilot to production",
    "pilots to production", "experimentation to production", "unlock",
    "supercharge", "next-generation", "next generation", "cutting-edge",
    "cutting edge", "seamless", "game-changing", "game changer", "revolutionize",
    "leverage", "best-in-class", "world-class", "unmatched", "unparalleled",
    "industry-leading", "industry leading", "blazing", "turbocharge",
    "full-stack", "vertically integrated",
]

DISPLACEMENT = [
    "chose us over", "chose nebius over", "switched from", "migrated away",
    "migrate away", "replace your cloud", "rip and replace", "rip-and-replace",
    "fell short", "gpus retired", "hyperscalers cannot", "hyperscalers can't",
    "ditch ", "leave aws", "leave your cloud",
]

HARD_BLOCK = {
    r"\bcaptions\b": "Captions is closed-lost: never reference it.",
    r"clustermax[^.\n]{0,40}\bgold\b": "ClusterMAX Gold is stale. Nebius is Platinum (ClusterMAX 3.0).",
    r"\bonly\b[^.\n]{0,60}\bplatinum\b|\bplatinum\b[^.\n]{0,60}\bonly\b": "Never pair 'only' with Platinum. Two providers were rated Platinum.",
    r"tpn gold shield": "Nebius does not hold TPN Gold Shield: no equivalence claims.",
    r"\bno models\b|\bnever compete": "Neutrality only in the framework's narrow form.",
    r"\b(guaranteed|absolute(ly)? secure|fully compliant|automatic(ally)? compliant)\b": "No absolute safety or automatic compliance claims.",
    r"semianalysis\.com": "Link Nebius's own ClusterMAX post, never the paywalled article.",
}

WARN_PATTERNS = {
    r"\b(black forest labs|runway|world labs)\b": "Target accounts are never shown as customers. Check the context.",
    r"\b(first|only|largest|fastest|leading)\b": "Superlative: needs a linked third-party or partner source and an 'as of' date.",
    r"\bup to\b": "'Up to' needs a stated baseline and source.",
    r"\b(shopify|ultimate bots|thestage|wildflow|lynx analytics|voxel51|sglang|brave)\b": "Non-M&E proof (archived E9 to E16): not allowed in M&E assets.",
    r"\badditive\b": "Don't just say 'additive'. Fill the template: we add [workload] when [condition], measured by [metric].",
}

APPROVED_CTAS = [
    "benchmark your game ai or media workload",
    "plan capacity for your next training run",
    "evaluate your model-serving deployment",
    "review your ip and data-protection requirements",
]

CTA_TYPES = {1, 2, 3, 4, 5, 6, 8, 9, 11, 12, 14, 15, 16, 17, 19}

HEADLINE_MAX_WORDS = {1: 10, 2: 12, 3: 12, 4: 16, 5: 14, 6: 16, 7: 16, 8: 14,
                      9: 12, 10: 20, 11: 10, 12: 12, 14: 10, 15: 20, 16: 10,
                      17: 16, 18: 16, 19: 12}

REQUIRED_SECTIONS = {
    4: [r"challenge", r"(solution|approach)", r"result", r"(what we learned|what did not|what didn't|lessons|what surprised)"],
    6: [r"(method|methodology|how we (tested|measured)|setup|configuration)"],
    10: [r"(about nebius|boilerplate)"],
}

METRIC_RE = re.compile(
    r"((?<![A-Za-z\d])\d[\d,.]*\s?(%|x\b|×|ms\b|s\b|seconds?|minutes?|hours?|days?|weeks?|tb\b|pb\b|gb\b|m\+|b\+|k\b|million|billion|gpus?\b|languages|genres))"
    r"|(\$\s?\d)",
    re.IGNORECASE,
)
SOURCE_RE = re.compile(r"\[src:[^\]]+\]|\[\^[^\]]+\]", re.IGNORECASE)
PLACEHOLDER_RE = re.compile(r"\[(?!src:)(?!\^)[^\]]*(metric|placeholder|tbd|todo|cleared|approved|customer|insert|date|price|confirm|pending)[^\]]*\]", re.IGNORECASE)


def strip_front_matter(text):
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            return text[end + 4:]
    return text


def sentences(text):
    for ln_no, line in enumerate(text.split("\n"), 1):
        st = line.strip()
        if not st or st.startswith(("<!--", "|---")) or re.match(r"\[\^[^\]]+\]:", st):
            continue
        for s in re.split(r"(?<=[.!?])\s+", line):
            if s.strip():
                yield ln_no, s


def line_of(text, idx):
    return text[:idx].count("\n") + 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--type", type=int, default=None)
    ap.add_argument("--final", action="store_true")
    ap.add_argument("--ignore-quotes", action="store_true")
    a = ap.parse_args()

    body = strip_front_matter(open(a.path, encoding="utf-8").read())
    if a.ignore_quotes:
        # blank out quoted spans but keep offsets and newlines
        body = re.sub(r'"[^"\n]*"', lambda m: '"' + " " * (len(m.group(0)) - 2) + '"', body)
    low = body.lower()
    errors, warns, notes = [], [], []

    for i, line in enumerate(body.split("\n"), 1):
        if EM_DASH in line:
            errors.append(f"L{i}: em-dash found. Use a colon, period, comma or parentheses.")
        if EN_DASH in line:
            warns.append(f"L{i}: en-dash found. Prefer 'to' for ranges, a hyphen for compounds.")

    for pat, msg in HARD_BLOCK.items():
        for m in re.finditer(pat, low):
            errors.append(f"L{line_of(low, m.start())}: '{m.group(0)}': {msg}")

    for ph in BANNED_PHRASES:
        for m in re.finditer(r"\b" + re.escape(ph) + r"\b", low):
            warns.append(f"L{line_of(low, m.start())}: cliche '{ph}'. Replace with a specific noun, verb or number.")
    for ph in DISPLACEMENT:
        for m in re.finditer(re.escape(ph), low):
            errors.append(f"L{line_of(low, m.start())}: displacement language '{ph.strip()}'. Nebius is added alongside incumbents.")

    for pat, msg in WARN_PATTERNS.items():
        for m in re.finditer(pat, low):
            warns.append(f"L{line_of(low, m.start())}: '{m.group(0)}': {msg}")

    unsourced = 0
    for ln, s in sentences(body):
        if s.lstrip().startswith("#"):
            continue
        if METRIC_RE.search(s) and re.search(r"\breactor\b", s, re.I):
            errors.append(f"L{ln}: Reactor result: stays out of public copy until publication clearance: \"{s.strip()[:90]}\"")
        if METRIC_RE.search(s) and not SOURCE_RE.search(s):
            unsourced += 1
            (errors if a.final else warns).append(
                f"L{ln}: metric without [src: ...] or footnote: \"{s.strip()[:90]}\"")

    for m in PLACEHOLDER_RE.finditer(body):
        (errors if a.final else notes).append(f"L{line_of(body, m.start())}: placeholder still open: {m.group(0)}")

    t = a.type
    if t:
        h1 = re.search(r"^#\s+(.+)$", body, re.MULTILINE)
        if h1:
            words = len(h1.group(1).split())
            lim = HEADLINE_MAX_WORDS.get(t)
            if lim and words > lim:
                warns.append(f"Headline has {words} words (limit {lim} for type {t:02d}).")
        else:
            notes.append("No H1 headline found.")
        if t in CTA_TYPES and not any(c in low for c in APPROVED_CTAS):
            warns.append("No approved Copy Kit CTA found. Add one as the purpose line.")
        for req in REQUIRED_SECTIONS.get(t, []):
            if not re.search(r"^#{2,4}.*" + req, low, re.MULTILINE):
                warns.append(f"Missing a required section matching /{req}/ for type {t:02d}.")
        if t == 14:
            limits = {"headline": 70, "intro": 150, "primary text": 150, "description": 100}
            for i, line in enumerate(body.split("\n"), 1):
                m = re.match(r"\s*[-*]?\s*\**(headline|intro|primary text|description)\**\s*:\s*(.+)", line, re.I)
                if m:
                    field, txt = m.group(1).lower(), SOURCE_RE.sub("", m.group(2)).strip()
                    if len(txt) > limits[field]:
                        warns.append(f"L{i}: ad {field} is {len(txt)} chars (target {limits[field]} or less).")
        if "platinum" in low and "nebius-platinum-clustermax-3-0" not in low:
            warns.append("ClusterMAX mention without a link to nebius.com/blog/posts/nebius-platinum-clustermax-3-0.")

    print(f"Lint report: {a.path}" + (f" (type {t:02d})" if t else "") + (" [final]" if a.final else ""))
    for label, items in (("ERROR", errors), ("WARN", warns), ("NOTE", notes)):
        for it in items:
            print(f"  {label}  {it}")
    print(f"Summary: {len(errors)} errors, {len(warns)} warnings, {len(notes)} notes, {unsourced} unsourced metric sentences.")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
