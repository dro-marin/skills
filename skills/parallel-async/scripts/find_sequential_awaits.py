#!/usr/bin/env python3
"""Find candidate unnecessary sequential awaits in a TS/JS repo (triage, not a fixer).

Heuristic and statement-based (understands strings, template literals and brackets, not a full
parser). Kinds:
  SEQ    two or more awaited statements in one block where a later one uses no name bound by an
         earlier one (or by lines between them). Strongest signal.
  GATED  the same, but an early return/throw/if sits between them (e.g. `if (!row) return null`).
         Can still be parallelised by starting the read early and reading it after the gate,
         but only when the read is cheap, read-only and safe to run for callers who fail the gate.
  LOOP   an await inside a for/while loop or forEach/reduce callback (one-at-a-time / N+1).
Flags: W = touches writes/sends (check ordering + atomicity); xN = chain length.

Every hit needs a read: the scanner cannot see side effects, transactions, single-connection
clients, auth gates hidden in helpers, rate limits or ordering requirements.

Usage: find_sequential_awaits.py <repo-or-dir> [--all] [--json] [--limit N] [--kind SEQ,GATED,LOOP]
  --all          include cold paths (scripts, tests, migrations, static client bundles)
  --auth-gated   also list GATED runs whose first read looks like auth/permission/rate-limit/cache
                 (hidden by default: that gate is usually supposed to stay first)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

EXTS = {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".mts"}
SKIP_DIRS = {"node_modules", ".next", ".open-next", ".wrangler", "dist", "build", "out", "coverage",
             ".git", ".turbo", ".vercel", "playwright-report", "test-results", ".worktrees", "vendor"}
COLD = re.compile(r"(^|/)(diag|scripts?|e2e|tests?|__tests__|__mocks__|migrations?|seed|fixtures?|one-off|tools|public|static)(/|$)"
                  r"|(^|/)local-qa[^/]*$|\.(test|spec|stories|config)\.[cm]?[jt]sx?$|\.d\.ts$|\.min\.js$")
HOT = [(re.compile(r"(^|/)(middleware|proxy)\.[jt]s$"), 5),
       (re.compile(r"(^|/)(page|layout|route|loader|actions?|template)\.[jt]sx?$"), 4),
       (re.compile(r"(^|/)(api|functions|routes?|handlers?)(/|$)"), 4),
       (re.compile(r"(^|/)(lib|server|db|queries|services?|_lib)(/|$)"), 2),
       (re.compile(r"(^|/)(src|app)(/|$)"), 1)]

CONTROL = re.compile(r"^\s*(?:\}\s*)?(?:if|else|for|while|do|switch|try|catch|finally|case|default)\b")
GATE = re.compile(r"^\s*(?:(?:\}\s*)?(?:if|else|switch|case|default|try|catch|finally)\b|return\b|throw\b|break\b|continue\b|\})")
LOOP_HEAD = re.compile(r"^\s*(?:for\s*(?:await\s*)?\(|while\s*\(|do\s*\{)|\.(?:forEach|reduce)\(\s*async\b")
DECL = re.compile(r"^\s*(?:export\s+)?(?:const|let|var)\s+(\{[^=]*?\}|\[[^=]*?\]|[A-Za-z_$][\w$]*)\s*(?::[^=]+)?=")
ASSIGN = re.compile(r"^\s*(\[[^=]*?\]|[A-Za-z_$][\w$.]*)\s*=(?!=)")
WRITE = re.compile(r"\b(insert|update|delete|upsert|\.run\(|\.batch\(|\.put\(|send\w*|create\w*|remove|post|patch|commit|exec|enqueue|publish|charge|refund)\b", re.I)
AUTHISH = re.compile(r"session|auth|permission|access|role|member|require|\bcan[A-Z_]|verif|allow|token|rateLimit|rate_limit|quota|gate|guard|onboard|entitle|caches?\b|\.match\(", re.I)
FREE = re.compile(r"^\s*(?:\(\s*)?await\s+(?:props\.)?(?:params|searchParams|import\s*\(|cookies\(\)|headers\(\)|Promise\.resolve|(?:new\s+Promise|sleep|wait|delay|frame|tick)\b)")
PARALLEL = re.compile(r"Promise\.(all|allSettled|race|any)\b")
ALL_GATED = False
IDENT = re.compile(r"[A-Za-z_$][\w$]*")
NOISE = {"await", "const", "let", "var", "return", "new", "true", "false", "null", "undefined", "this",
         "as", "typeof", "async", "function", "of", "in", "if", "else", "sql", "db", "env", "c", "ctx"}


def code_only(text: str) -> str:
    """Blank out comments and string/template contents but keep ${...} expressions."""
    out, i, n, stack = [], 0, len(text), []  # stack of '`' (template) or '{' (brace inside ${})
    while i < n:
        ch = text[i]
        in_tpl = stack and stack[-1] == "`"
        if in_tpl:
            if ch == "\\":
                out.append("  "); i += 2; continue
            if ch == "`":
                stack.pop(); out.append("`"); i += 1; continue
            if text.startswith("${", i):
                stack.append("{"); out.append("${"); i += 2; continue
            out.append("\n" if ch == "\n" else " "); i += 1; continue
        if text.startswith("//", i):
            j = text.find("\n", i); j = n if j < 0 else j
            out.append(" " * (j - i)); i = j; continue
        if text.startswith("/*", i):
            j = text.find("*/", i + 2); j = n if j < 0 else j + 2
            out.append(re.sub(r"[^\n]", " ", text[i:j])); i = j; continue
        if ch in "'\"":
            j = i + 1
            while j < n and text[j] != ch and text[j] != "\n":
                j += 2 if text[j] == "\\" else 1
            if j >= n or text[j] == "\n":  # unterminated (JSX text, regex): blank to end of line, keep the newline
                out.append(" " * (j - i)); i = j; continue
            out.append(ch + " " * (j - i - 1) + ch); i = j + 1; continue
        if ch == "`":
            stack.append("`"); out.append("`"); i += 1; continue
        if ch == "{" and stack and stack[-1] == "{":
            stack.append("{")
        elif ch == "}" and stack and stack[-1] == "{":
            stack.pop()
            out.append("}"); i += 1; continue
        out.append(ch); i += 1
    return "".join(out)


def names(lhs: str | None) -> set[str]:
    if not lhs:
        return set()
    if lhs.startswith("{"):
        lhs = re.sub(r"[A-Za-z_$][\w$]*\s*:", "", lhs)  # { a: b } binds b
    return {n for n in IDENT.findall(lhs) if n not in NOISE}


def opens_block(s: str) -> bool:
    """Line ends with a `{` that opens a code block, not an object literal."""
    s = s.rstrip()
    if not s.endswith("{") or s.endswith("${"):
        return False
    before = s[:-1].rstrip()
    return not (before == "" or before.endswith(("(", "=", "[", ",", ":", "?", "||", "&&", "??", "return", "=> ({", "<"))
                or re.search(r"\b(?:return|yield|await|typeof|in|of)$", before))


def statements(code: list[str]):
    """Yield (start, end, kind) where kind is 'head' (block opener, body not swallowed) or 'stmt'."""
    i, n = 0, len(code)
    while i < n:
        s = code[i].strip()
        if not s:
            i += 1; continue
        if CONTROL.match(code[i]) or opens_block(s):
            yield i, i, "head"; i += 1; continue
        depth, ticks, j = 0, 0, i
        while j < n:
            line = code[j]
            if j > i and opens_block(line):
                break
            depth += line.count("(") + line.count("[") + line.count("{") - line.count(")") - line.count("]") - line.count("}")
            ticks += line.count("`")
            t = line.rstrip()
            nxt = code[j + 1].strip() if j + 1 < n else ""
            cont = t.endswith(("=", "?", ":", "(", ",", "&&", "||", "+", "`", "=>", "??")) or nxt.startswith((".", "?", ":", "&&", "||", "??", "+"))
            if depth <= 0 and not cont and ticks % 2 == 0:
                break
            if depth < 0 or j - i > 60:
                break
            j += 1
        if j < n and j > i and opens_block(code[j]):
            yield i, j, "head"  # multi-line signature or call ending in a block: don't swallow the body
            i = j + 1
            continue
        yield i, min(j, n - 1), "stmt"
        i = min(j, n - 1) + 1


def scan_file(path: Path, rel: str) -> list[dict]:
    try:
        raw = path.read_text(errors="ignore")
    except OSError:
        return []
    if "await" not in raw:
        return []
    src = raw.splitlines()
    code = code_only(raw).splitlines()
    code += [""] * (len(src) - len(code))
    hits: list[dict] = []
    loops: list[int] = []
    run = None  # dict: start, indent, bound, texts, gated, write, count
    indent = lambda k: len(code[k]) - len(code[k].lstrip())

    def flush():
        nonlocal run
        if run and run["count"] >= 2 and run["indep"] and not (run["gated"] and run["authish"] and not ALL_GATED):
            hits.append({"kind": "GATED" if run["gated"] else "SEQ", "line": run["start"] + 1, "line2": run["last"] + 1,
                         "chain": run["count"], "write": run["write"], "text": "  ||  ".join(run["texts"][:3])})
        run = None

    for a, b, kind in statements(code):
        text = "\n".join(code[a:b + 1])
        raw_text = "\n".join(src[a:b + 1])
        ind = indent(a)
        while loops and ind <= loops[-1] and not code[a].strip().startswith((")",)):
            loops.pop()
        if kind == "head":
            if LOOP_HEAD.search(code[a]):
                loops.append(ind)
                flush()
            elif run and ind == run["indent"] and GATE.match(code[a]):
                run["gate_pending"] = True
            elif run and ind < run["indent"]:
                flush()
            if "await" in text and loops and ind > loops[-1]:
                hits.append({"kind": "LOOP", "line": a + 1, "text": src[a].strip()[:140]})
            continue
        if run and ind < run["indent"]:
            flush()
        has_await = re.search(r"\bawait\b", text) is not None
        if has_await and loops and ind > loops[-1] and not PARALLEL.search(text):
            hits.append({"kind": "LOOP", "line": a + 1, "text": src[a].strip()[:140]})
        if LOOP_HEAD.search(text) and "await" in text and not PARALLEL.search(text):  # e.g. items.forEach(async x => { await ... })
            hits.append({"kind": "LOOP", "line": a + 1, "text": src[a].strip()[:140]})
            continue
        stripped = code[a].strip()
        if GATE.match(code[a]) or stripped.startswith(("return", "throw")):
            if run and ind == run["indent"]:
                run["gate_pending"] = True
            continue
        if not has_await or PARALLEL.search(text) or re.match(r"^(?:export\s+)?(?:async\s+)?function\b", stripped) \
                or re.search(r"=\s*(?:async\s*)?(?:\([^)]*\)|[A-Za-z_$][\w$]*)\s*=>", text.split("\n")[0]):
            d = DECL.match(code[a]) or ASSIGN.match(code[a])
            if run and ind == run["indent"] and d and set(IDENT.findall(text)) & run["bound"]:
                run["bound"] |= names(d.group(1))  # derived value: still dependent
            continue
        d = DECL.match(code[a]) or ASSIGN.match(code[a])
        bound = names(d.group(1)) if d else set()
        rhs = text[d.end():] if d else text
        if FREE.match(rhs) or FREE.match(text):
            if run and ind == run["indent"]:
                run["bound"] |= bound
            continue
        used = set(IDENT.findall(rhs)) - NOISE
        first = src[a].strip()[:100]
        is_write = bool(WRITE.search(raw_text))
        if run and ind == run["indent"]:
            if used & run["bound"] or run.get("prev_effect"):  # data dependency, or ordered after a bare `await effect()`
                flush()
                run = {"start": a, "last": b, "indent": ind, "bound": bound, "texts": [first], "gated": False,
                       "write": bool(WRITE.search(raw_text)), "count": 1, "indep": False, "authish": bool(AUTHISH.search(text))}
            else:
                run.update(last=b, count=run["count"] + 1, indep=True, write=run["write"] or bool(WRITE.search(raw_text)),
                           gated=run["gated"] or run.get("gate_pending", False))
                run["bound"] |= bound
                run["texts"].append(first)
            run["prev_effect"] = not bound
        else:
            flush()
            run = {"start": a, "last": b, "indent": ind, "bound": bound, "texts": [first], "gated": False,
                   "write": bool(WRITE.search(raw_text)), "count": 1, "indep": False, "authish": bool(AUTHISH.search(text))}
            run["prev_effect"] = not bound
    flush()
    for h in hits:
        h["file"] = rel
    return hits


def heat(rel: str) -> int:
    return sum(w for rx, w in HOT if rx.search(rel))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("repo")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--limit", type=int, default=400)
    ap.add_argument("--kind", default="SEQ,GATED,LOOP")
    ap.add_argument("--auth-gated", action="store_true", help="also list GATED runs whose gate looks like auth/permission/rate-limit/cache (usually correct as-is)")
    a = ap.parse_args()
    global ALL_GATED
    ALL_GATED = a.auth_gated
    root = Path(a.repo).resolve()
    kinds = set(a.kind.upper().split(","))
    hits = []
    for dp, dns, fns in os.walk(root):
        dns[:] = [d for d in dns if d not in SKIP_DIRS and not d.startswith(".")]
        for f in fns:
            p = Path(dp) / f
            if p.suffix not in EXTS:
                continue
            rel = str(p.relative_to(root))
            if not a.all and COLD.search(rel):
                continue
            for h in scan_file(p, rel):
                if h["kind"] in kinds:
                    h["heat"] = heat(rel)
                    hits.append(h)
    order = {"SEQ": 0, "GATED": 1, "LOOP": 2}
    hits.sort(key=lambda h: (-h["heat"], order[h["kind"]], h["file"], h["line"]))
    total = len(hits)
    hits = hits[: a.limit]
    if a.json:
        json.dump(hits, sys.stdout, indent=1)
        print()
        return 0
    if not hits:
        print("no candidates")
        return 0
    for h in hits:
        tag = h["kind"] + (f"x{h['chain']}" if h.get("chain", 0) > 2 else "") + (" W" if h.get("write") else "")
        loc = f"{h['file']}:{h['line']}" + (f"-{h['line2']}" if h.get("line2") else "")
        print(f"[{h['heat']}] {tag:9} {loc}\n          {h['text']}")
    c = {k: sum(h["kind"] == k for h in hits) for k in order}
    more = f" (showing {len(hits)} of {total})" if total > len(hits) else ""
    print(f"\n{len(hits)} candidates{more}: {c['SEQ']} SEQ, {c['GATED']} GATED, {c['LOOP']} LOOP. "
          "[n] = hot-path score. W = touches writes/sends: check ordering and atomicity.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
