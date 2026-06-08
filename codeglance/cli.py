"""Command-line interface for CODEGLANCE.

Subcommands:
  map        Build the full onboarding map (packages + hotspots + files).
  hotspots   Just the ranked files to read first.
  deps       Internal dependency edges (source -> dependency).

Global: --version, --format {table,json}.

Returns 0 on success, non-zero on failure.
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import List, Optional

from . import TOOL_NAME, TOOL_VERSION
from .core import build_map


def _print_table_map(rmap) -> None:
    s = rmap.to_dict()["summary"]
    print(f"CODEGLANCE map for {rmap.root}")
    print(f"  files={s['files']}  code_lines={s['code_lines']}  packages={s['packages']}")
    langs = ", ".join(f"{k}:{v}" for k, v in sorted(s["languages"].items()))
    print(f"  languages: {langs}")
    print()
    print("Packages:")
    for pkg, paths in sorted(rmap.packages.items()):
        print(f"  {pkg}/  ({len(paths)} files)")
    print()
    _print_table_hotspots(rmap.hotspots)


def _print_table_hotspots(hotspots) -> None:
    print("Hotspots (read these first):")
    print(f"  {'score':>6}  {'fanin':>5}  {'cx':>4}  {'lines':>5}  path")
    for f in hotspots:
        print(
            f"  {f.score:6.1f}  {len(f.dependents):5d}  {f.complexity:4d}  "
            f"{f.code_lines:5d}  {f.path}"
        )


def _print_table_deps(rmap) -> None:
    print("Internal dependency edges (source -> dep):")
    any_edge = False
    for f in rmap.files:
        for dep in f.deps:
            print(f"  {f.path} -> {dep}")
            any_edge = True
    if not any_edge:
        print("  (no internal edges resolved)")


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog=TOOL_NAME,
        description="Repo onboarding map: architecture + hotspots for humans and agents.",
    )
    p.add_argument("--version", action="version",
                   version=f"{TOOL_NAME} {TOOL_VERSION}")
    p.add_argument("--format", choices=("table", "json"), default="table",
                   help="output format (default: table)")
    sub = p.add_subparsers(dest="command", required=True)

    pm = sub.add_parser("map", help="full onboarding map")
    pm.add_argument("path", nargs="?", default=".", help="repo root (default: .)")

    ph = sub.add_parser("hotspots", help="ranked files to read first")
    ph.add_argument("path", nargs="?", default=".", help="repo root (default: .)")
    ph.add_argument("--top", type=int, default=10, help="how many (default: 10)")

    pd = sub.add_parser("deps", help="internal dependency edges")
    pd.add_argument("path", nargs="?", default=".", help="repo root (default: .)")

    return p


def main(argv: Optional[List[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        rmap = build_map(args.path)
    except (FileNotFoundError, NotADirectoryError) as exc:
        print(f"{TOOL_NAME}: error: not a directory: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"{TOOL_NAME}: error: {exc}", file=sys.stderr)
        return 1

    if args.command == "hotspots":
        from .core import rank_hotspots
        hotspots = rank_hotspots(rmap.files, top=args.top)
        if args.format == "json":
            print(json.dumps([h.to_dict() for h in hotspots], indent=2))
        else:
            _print_table_hotspots(hotspots)
        return 0

    if args.command == "deps":
        if args.format == "json":
            edges = [
                {"source": f.path, "dep": dep}
                for f in rmap.files for dep in f.deps
            ]
            print(json.dumps(edges, indent=2))
        else:
            _print_table_deps(rmap)
        return 0

    # map
    if args.format == "json":
        print(json.dumps(rmap.to_dict(), indent=2))
    else:
        _print_table_map(rmap)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
