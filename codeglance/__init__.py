"""CODEGLANCE — repo onboarding map: architecture + hotspots for humans and agents.

Scans a codebase and produces a compact, machine-and-human readable map of its
structure: per-directory module groupings, per-file size/complexity/import-degree
metrics, dependency edges between internal modules, and a ranked list of
"hotspots" (files most worth reading first when onboarding).

Standard library only. No network. No install.
"""
from .core import (
    scan_repo,
    build_map,
    rank_hotspots,
    RepoMap,
    FileInfo,
)

TOOL_NAME = "codeglance"
TOOL_VERSION = "1.0.0"

__all__ = [
    "scan_repo",
    "build_map",
    "rank_hotspots",
    "RepoMap",
    "FileInfo",
    "TOOL_NAME",
    "TOOL_VERSION",
]
