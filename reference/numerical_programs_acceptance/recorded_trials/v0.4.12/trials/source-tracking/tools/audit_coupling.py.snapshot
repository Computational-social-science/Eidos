#!/usr/bin/env python
"""Measure how coupled the framework's modules actually are.

WHY THIS EXISTS
    "Loosely coupled" is a claim like any other: it needs a measurement. This walks the
    real import graph (AST, not grep), separates imports made at module scope (hard)
    from imports made inside a function (soft, the escape hatch that keeps an optional
    dependency optional), and reports cycles, fan-in and fan-out.

WHAT COUNTS AS COUPLING HERE
    * hard edge  -- importing at module scope: the target must import for the source to
                    import, so a failure propagates at import time.
    * soft edge  -- importing inside a function: the dependency is paid only on the code
                    path that needs it, and its absence can be caught.
    * process edge -- subprocess use: a boundary crossed by a CLI contract that no type
                    checker sees.
    * network edge -- urllib/socket: a boundary crossed by a wire format.

GATE
    Exit 1 when the internal graph has a cycle (an SCC larger than one module), because
    a cycle means neither module can be understood, tested or replaced alone.

WHAT IT DOES NOT DO
    It does not score "good" or "bad". A gate that imports every check is a coupling
    hub by design; the number to watch is cycles and hard edges into optional layers.
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# A Windows drive path or an MSYS absolute path. The lookbehind excludes "http://",
# whose "p:" would otherwise match as a drive letter.
ABS_PATH = re.compile(r"(?<![A-Za-z0-9])[A-Za-z]:[\\/]|/e/2026|/c/Users")


def module_name(path: Path) -> str:
    rel = path.relative_to(ROOT).with_suffix("")
    parts = list(rel.parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


class Imports(ast.NodeVisitor):
    """Collect imports with the scope they were written in."""

    def __init__(self, package: str):
        self.package = package
        self.depth = 0
        self.found: list[tuple[str, str, int]] = []  # (target, raw, depth)

    def _visit_function(self, node):
        self.depth += 1
        self.generic_visit(node)
        self.depth -= 1

    visit_FunctionDef = _visit_function
    visit_AsyncFunctionDef = _visit_function

    def visit_Import(self, node):
        for alias in node.names:
            self.found.append((alias.name, alias.name, self.depth))

    def visit_ImportFrom(self, node):
        base = node.module or ""
        if node.level:
            parts = self.package.split(".")
            keep = len(parts) - (node.level - 1)
            base = ".".join(parts[:keep] + ([base] if base else []))
        for alias in node.names:
            self.found.append((f"{base}.{alias.name}" if base else alias.name,
                               f"{base}.{alias.name}" if base else alias.name, self.depth))


def resolve(target: str, known: set[str]) -> str | None:
    """Map an import target onto a module in this repository, if it is one."""
    parts = target.split(".")
    for cut in range(len(parts), 0, -1):
        candidate = ".".join(parts[:cut])
        if candidate in known:
            return candidate
    return None


def resolve_base(node: ast.ImportFrom, package: str) -> str:
    """The absolute module an ImportFrom refers to, honouring relative imports."""
    base = node.module or ""
    if node.level:
        parts = package.split(".")
        keep = len(parts) - (node.level - 1)
        base = ".".join(parts[:keep] + ([base] if base else []))
    return base


def collect_symbols(files: list[Path], known: set[str]):
    """Public names each module defines, and which of them are imported elsewhere."""
    defined: dict[str, set[str]] = {m: set() for m in known}
    used: dict[str, set[str]] = defaultdict(set)
    for path in files:
        name = module_name(path)
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                if not node.name.startswith("_"):
                    defined[name].add(node.name)
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id.isupper():
                        defined[name].add(target.id)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                base = resolve(resolve_base(node, name), known)
                if base and base != name:
                    for alias in node.names:
                        if alias.name != "*":
                            used[base].add(alias.name)
    return defined, used


def tarjan(nodes: list[str], edges: dict[str, set[str]]) -> list[list[str]]:
    index: dict[str, int] = {}
    low: dict[str, int] = {}
    stack: list[str] = []
    on_stack: set[str] = set()
    out: list[list[str]] = []
    counter = 0

    def strong(v: str):
        nonlocal counter
        index[v] = low[v] = counter
        counter += 1
        stack.append(v)
        on_stack.add(v)
        for w in edges.get(v, ()):  # noqa: B007
            if w not in index:
                strong(w)
                low[v] = min(low[v], low[w])
            elif w in on_stack:
                low[v] = min(low[v], index[w])
        if low[v] == index[v]:
            component = []
            while True:
                w = stack.pop()
                on_stack.discard(w)
                component.append(w)
                if w == v:
                    break
            out.append(component)

    for v in nodes:
        if v not in index:
            strong(v)
    return [c for c in out if len(c) > 1]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", metavar="PATH")
    ap.add_argument("--symbols", action="store_true",
                    help="also report each module's public surface and how much of it is consumed")
    args = ap.parse_args()

    files = sorted(p for p in list((ROOT / "framework").rglob("*.py")) + list((ROOT / "tools").glob("*.py"))
                   if "__pycache__" not in p.parts)
    known = {module_name(p) for p in files}
    known |= {"framework", "framework.inference"}

    hard: dict[str, set[str]] = defaultdict(set)
    soft: dict[str, set[str]] = defaultdict(set)
    process: dict[str, int] = defaultdict(int)
    network: dict[str, int] = defaultdict(int)
    absolute: dict[str, int] = defaultdict(int)
    env: dict[str, int] = defaultdict(int)

    for path in files:
        name = module_name(path)
        source = path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(source)
        visitor = Imports(name)
        visitor.visit(tree)
        for target, _raw, depth in visitor.found:
            resolved = resolve(target, known)
            if not resolved or resolved == name:
                continue
            (hard if depth == 0 else soft)[name].add(resolved)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                if any(a.name.split(".")[0] in {"subprocess"} for a in node.names):
                    process[name] += 1
                if any(a.name.split(".")[0] in {"urllib", "socket", "http"} for a in node.names):
                    network[name] += 1
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                if ABS_PATH.search(node.value):
                    absolute[name] += 1
            elif (isinstance(node, ast.Attribute) and node.attr == "environ"
                  and isinstance(node.value, ast.Name) and node.value.id == "os"):
                env[name] += 1

    nodes = sorted({module_name(p) for p in files})
    for n in nodes:
        hard.setdefault(n, set())
        soft.setdefault(n, set())
    all_edges = {n: set(hard.get(n, ())) | set(soft.get(n, ())) for n in nodes}
    cycles = tarjan(nodes, all_edges)

    fan_out = {n: (len(hard.get(n, ())), len(soft.get(n, ()))) for n in nodes}
    fan_in: dict[str, int] = defaultdict(int)
    for n in nodes:
        for dep in all_edges.get(n, ()):
            fan_in[dep] += 1

    print(f"modules: {len(nodes)}   hard edges: {sum(len(v) for v in hard.values())}   "
          f"soft edges: {sum(len(v) for v in soft.values())}")
    print("\nmost depended-on (fan-in):")
    for n, count in sorted(fan_in.items(), key=lambda kv: -kv[1])[:6]:
        hard_in = sum(1 for src in nodes if n in hard.get(src, ()))
        print(f"  {n:<28} {count:2d} total, {hard_in} hard")

    print("\nwidest importers (hard/soft out):")
    for n, (h, s) in sorted(fan_out.items(), key=lambda kv: -(kv[1][0] + kv[1][1]))[:6]:
        print(f"  {n:<28} {h} hard, {s} soft")

    print("\nprocess / network / absolute-path / env:")
    for n in nodes:
        if process[n] or network[n] or absolute[n] or env[n]:
            print(f"  {n:<28} subprocess={process[n]} network={network[n]} "
                  f"abs_path={absolute[n]} env={env[n]}")

    if cycles:
        print("\nCYCLES (each list is a strongly connected component):")
        for component in cycles:
            print("  " + " <-> ".join(sorted(component)))
    else:
        print("\ncycles: none")

    symbol_table = {}
    if args.symbols:
        defined, used = collect_symbols(files, known)
        print("\npublic surface (framework modules):")
        total_pub = total_used = 0
        for module in sorted(defined):
            if not module.startswith("framework.") or not defined[module]:
                continue
            pub = defined[module]
            consumed = pub & used.get(module, set())
            total_pub += len(pub)
            total_used += len(consumed)
            spare = sorted(pub - consumed)
            note = f"  unused: {', '.join(spare[:6])}" if spare else ""
            print(f"  {module:<28} public {len(pub):2d}  used {len(consumed):2d}{note}")
            symbol_table[module] = {"public": sorted(pub), "used": sorted(consumed)}
        if total_pub:
            print(f"  -> {total_used}/{total_pub} public names consumed "
                  f"({total_used / total_pub:.0%})")

    if args.json:
        out = Path(args.json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({
            "modules": len(nodes),
            "hard": {k: sorted(v) for k, v in hard.items()},
            "soft": {k: sorted(v) for k, v in soft.items()},
            "fan_in": dict(fan_in),
            "cycles": cycles,
            "process": {k: v for k, v in process.items() if v},
            "network": {k: v for k, v in network.items() if v},
            "absolute_paths": {k: v for k, v in absolute.items() if v},
            "env_reads": {k: v for k, v in env.items() if v},
            "symbols": symbol_table,
        }, indent=2), encoding="utf-8")

    return 1 if cycles else 0


if __name__ == "__main__":
    raise SystemExit(main())
