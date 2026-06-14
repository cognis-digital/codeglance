"""Core engine for CODEGLANCE.

Real logic, no stubs. The engine:
  1. Walks a directory tree, skipping vendor/VCS/build noise.
  2. For each source file, computes line count, a cheap cyclomatic-style
     complexity estimate, and the set of internal modules it imports.
  3. Resolves imports into an internal dependency graph (who-depends-on-whom).
  4. Ranks hotspots = files that are large AND complex AND heavily depended-on,
     i.e. the files an onboarding human or agent should read first.

Python files get real AST analysis. Other recognized languages get a
lightweight regex/heuristic pass so the map still covers polyglot repos.
"""
from __future__ import annotations

import ast
import os
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

# Directories that never contain code worth onboarding on.
SKIP_DIRS = {
    ".git", ".hg", ".svn", "__pycache__", ".mypy_cache", ".pytest_cache",
    ".tox", ".venv", "venv", "env", "node_modules", "dist", "build",
    ".idea", ".vscode", "site-packages", ".eggs", "target", ".next",
    "coverage", ".cache",
}

# Extensions we treat as source, mapped to a language label.
LANG_BY_EXT = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".rb": "ruby",
    ".c": "c",
    ".h": "c",
    ".cc": "cpp",
    ".cpp": "cpp",
    ".hpp": "cpp",
    ".sh": "shell",
}

# Keywords that introduce a branch — used for the language-agnostic
# complexity estimate on non-Python files.
_BRANCH_RE = re.compile(
    r"\b(if|elif|else if|for|while|case|catch|except|&&|\|\||\?)\b|\?\s*[^:]"
)


@dataclass
class FileInfo:
    """Per-file metrics and resolved internal dependencies."""
    path: str               # repo-relative, forward-slashed
    lang: str
    lines: int
    code_lines: int
    complexity: int         # cyclomatic-ish: 1 + number of branch points
    defs: int               # functions/classes/top-level definitions
    imports: List[str] = field(default_factory=list)   # raw import targets
    deps: List[str] = field(default_factory=list)       # resolved internal paths
    dependents: List[str] = field(default_factory=list) # who imports me
    score: float = 0.0

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "lang": self.lang,
            "lines": self.lines,
            "code_lines": self.code_lines,
            "complexity": self.complexity,
            "defs": self.defs,
            "deps": sorted(self.deps),
            "dependents": sorted(self.dependents),
            "fan_in": len(self.dependents),
            "fan_out": len(self.deps),
            "score": round(self.score, 2),
        }


@dataclass
class RepoMap:
    """The full onboarding map."""
    root: str
    files: List[FileInfo]
    languages: Dict[str, int]              # lang -> file count
    packages: Dict[str, List[str]]         # top dir -> file paths
    hotspots: List[FileInfo] = field(default_factory=list)

    def to_dict(self) -> dict:
        total_lines = sum(f.lines for f in self.files)
        total_code = sum(f.code_lines for f in self.files)
        return {
            "root": self.root,
            "summary": {
                "files": len(self.files),
                "total_lines": total_lines,
                "code_lines": total_code,
                "languages": self.languages,
                "packages": len(self.packages),
            },
            "packages": {
                pkg: sorted(paths) for pkg, paths in sorted(self.packages.items())
            },
            "hotspots": [f.to_dict() for f in self.hotspots],
            "files": [f.to_dict() for f in self.files],
        }


def _norm(path: str) -> str:
    return path.replace(os.sep, "/")


def _iter_source_files(root: str) -> List[str]:
    """Return repo-relative source file paths, skipping noise dirs."""
    out: List[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        # Prune skip dirs in place so os.walk does not descend.
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".egg")]
        for name in filenames:
            ext = os.path.splitext(name)[1].lower()
            if ext in LANG_BY_EXT:
                rel = os.path.relpath(os.path.join(dirpath, name), root)
                out.append(_norm(rel))
    return sorted(out)


def _read_text(abspath: str) -> str:
    try:
        with open(abspath, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return ""


def _count_lines(text: str) -> Tuple[int, int]:
    """Return (total_lines, non_blank_non_comment_lines)."""
    total = 0
    code = 0
    for raw in text.splitlines():
        total += 1
        s = raw.strip()
        if not s:
            continue
        if s.startswith(("#", "//", "/*", "*", "--")):
            continue
        code += 1
    return total, code


def _analyze_python(text: str) -> Tuple[int, int, List[str]]:
    """Return (complexity, defs, raw_import_targets) via AST."""
    try:
        tree = ast.parse(text)
    except SyntaxError:
        # Fall back to the heuristic path on unparseable Python.
        comp, defs = _heuristic_complexity(text)
        return comp, defs, _heuristic_imports(text)

    complexity = 1
    defs = 0
    imports: List[str] = []
    branch_nodes = (
        ast.If, ast.For, ast.AsyncFor, ast.While, ast.Try,
        ast.With, ast.AsyncWith, ast.BoolOp, ast.IfExp,
    )
    for node in ast.walk(tree):
        if isinstance(node, branch_nodes):
            complexity += 1
        elif isinstance(node, (ast.ExceptHandler,)):
            complexity += 1
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            defs += 1
        elif isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            # Preserve relative-import dots so resolution can use them.
            prefix = "." * (node.level or 0)
            imports.append(prefix + mod)
    return complexity, defs, imports


def _heuristic_complexity(text: str) -> Tuple[int, int]:
    complexity = 1 + len(_BRANCH_RE.findall(text))
    defs = len(re.findall(
        r"\b(func|function|def|class|interface|struct|impl|fn)\b", text
    ))
    return complexity, defs


def _heuristic_imports(text: str) -> List[str]:
    targets: List[str] = []
    # ES / TS imports
    for m in re.finditer(r"""(?:import|export)[^'\"]*from\s+['\"]([^'\"]+)['\"]""", text):
        targets.append(m.group(1))
    for m in re.finditer(r"""require\(\s*['\"]([^'\"]+)['\"]\s*\)""", text):
        targets.append(m.group(1))
    # Go / generic
    for m in re.finditer(r"""^\s*import\s+['\"]([^'\"]+)['\"]""", text, re.M):
        targets.append(m.group(1))
    return targets


def _analyze_file(abspath: str, rel: str) -> FileInfo:
    ext = os.path.splitext(rel)[1].lower()
    lang = LANG_BY_EXT.get(ext, "unknown")
    text = _read_text(abspath)
    total, code = _count_lines(text)
    if lang == "python":
        complexity, defs, imports = _analyze_python(text)
    else:
        complexity, defs = _heuristic_complexity(text)
        imports = _heuristic_imports(text)
    return FileInfo(
        path=rel,
        lang=lang,
        lines=total,
        code_lines=code,
        complexity=complexity,
        defs=defs,
        imports=imports,
    )


def scan_repo(root: str) -> List[FileInfo]:
    """Scan a repo root and return per-file metrics (no graph resolution yet)."""
    if not root or not isinstance(root, str):
        raise ValueError(f"root must be a non-empty string, got {root!r}")
    root = os.path.abspath(root)
    if not os.path.isdir(root):
        raise NotADirectoryError(f"Not a directory: {root!r}")
    infos: List[FileInfo] = []
    for rel in _iter_source_files(root):
        infos.append(_analyze_file(os.path.join(root, rel), rel))
    return infos


def _module_index(files: List[FileInfo]) -> Dict[str, str]:
    """Map candidate module keys -> file path for internal resolution.

    For Python a/b/c.py registers 'a.b.c' and 'a.b' (package via __init__).
    For other langs the path without extension and the basename are registered.
    """
    index: Dict[str, str] = {}
    for f in files:
        no_ext = f.path[: f.path.rfind(".")] if "." in f.path else f.path
        base = no_ext.split("/")[-1]
        # path-style keys
        index.setdefault(no_ext, f.path)
        index.setdefault(base, f.path)
        if f.lang == "python":
            dotted = no_ext.replace("/", ".")
            index.setdefault(dotted, f.path)
            if dotted.endswith(".__init__"):
                index.setdefault(dotted[: -len(".__init__")], f.path)
    return index


def _resolve_import(target: str, source: FileInfo, index: Dict[str, str]) -> Optional[str]:
    """Resolve a raw import target to an internal file path, or None."""
    if not target:
        return None
    # Relative ES import: ./foo, ../bar/baz
    if target.startswith(".") and "/" in target:
        src_dir = os.path.dirname(source.path)
        joined = _norm(os.path.normpath(os.path.join(src_dir, target)))
        for cand in (joined, joined + "/index"):
            if cand in index:
                return index[cand]
        base = joined.split("/")[-1]
        return index.get(base)
    # Python dotted (possibly relative with leading dots)
    if target.startswith("."):
        level = len(target) - len(target.lstrip("."))
        rest = target.lstrip(".")
        parts = source.path.split("/")[:-1]  # package dir of source
        if level > 1:
            parts = parts[: -(level - 1)] if (level - 1) <= len(parts) else []
        base_pkg = ".".join(parts)
        dotted = (base_pkg + "." + rest).strip(".") if rest else base_pkg
        if dotted in index:
            return index[dotted]
        # try trimming submodule (from x import y -> module x)
        if "." in dotted and dotted.rsplit(".", 1)[0] in index:
            return index[dotted.rsplit(".", 1)[0]]
        return None
    # Absolute: exact, then progressively trim trailing components.
    if target in index:
        return index[target]
    parts = target.replace("/", ".").split(".")
    while len(parts) > 1:
        parts = parts[:-1]
        key = ".".join(parts)
        if key in index:
            return index[key]
    return None


def build_map(root: str) -> RepoMap:
    """Scan + resolve dependency graph + rank hotspots into a RepoMap."""
    files = scan_repo(root)
    by_path = {f.path: f for f in files}
    index = _module_index(files)

    # Resolve dependency edges.
    for f in files:
        seen: Set[str] = set()
        for target in f.imports:
            resolved = _resolve_import(target, f, index)
            if resolved and resolved != f.path and resolved not in seen:
                seen.add(resolved)
        f.deps = sorted(seen)
        for dep in f.deps:
            by_path[dep].dependents.append(f.path)

    # Languages + packages.
    languages: Dict[str, int] = {}
    packages: Dict[str, List[str]] = {}
    for f in files:
        languages[f.lang] = languages.get(f.lang, 0) + 1
        top = f.path.split("/")[0] if "/" in f.path else "(root)"
        packages.setdefault(top, []).append(f.path)

    rmap = RepoMap(
        root=_norm(os.path.abspath(root)),
        files=files,
        languages=languages,
        packages=packages,
    )
    rmap.hotspots = rank_hotspots(files)
    return rmap


def rank_hotspots(files: List[FileInfo], top: int = 10) -> List[FileInfo]:
    """Score and return the files most worth reading first.

    Score = weighted blend of complexity, size, and fan-in (how many other
    internal files import it). Heavily-imported, complex, large files are the
    load-bearing modules an onboarding agent should read before anything else.
    """
    if not isinstance(top, int) or top < 1:
        raise ValueError(f"top must be a positive integer, got {top!r}")
    if not files:
        return []
    max_lines = max((f.code_lines for f in files), default=1) or 1
    max_comp = max((f.complexity for f in files), default=1) or 1
    max_fanin = max((len(f.dependents) for f in files), default=1) or 1
    for f in files:
        size_n = f.code_lines / max_lines
        comp_n = f.complexity / max_comp
        fanin_n = len(f.dependents) / max_fanin
        # Fan-in weighted highest: central modules matter most for onboarding.
        f.score = 100.0 * (0.45 * fanin_n + 0.35 * comp_n + 0.20 * size_n)
    ranked = sorted(files, key=lambda f: (f.score, len(f.dependents), f.complexity), reverse=True)
    return ranked[:top]
