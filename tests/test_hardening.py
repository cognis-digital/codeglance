"""Hardening tests: edge cases, bad input, and error paths."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest

from codeglance.cli import main
from codeglance.core import (
    FileInfo,
    build_map,
    rank_hotspots,
    scan_repo,
)

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEMO = os.path.join(REPO_ROOT, "demos", "01-basic")


class TestScanRepoInputValidation(unittest.TestCase):
    """scan_repo must reject bad inputs before touching the filesystem."""

    def test_empty_string_raises_value_error(self):
        with self.assertRaises(ValueError):
            scan_repo("")

    def test_none_raises_value_error(self):
        with self.assertRaises((ValueError, TypeError)):
            scan_repo(None)  # type: ignore[arg-type]

    def test_missing_path_raises_file_not_found(self):
        with self.assertRaises((FileNotFoundError, NotADirectoryError)):
            scan_repo("/no/such/directory/xyz_does_not_exist_42")

    def test_file_not_dir_raises_not_a_directory(self):
        # Pass a real file path (pyproject.toml) — must raise NotADirectoryError
        pyproject = os.path.join(REPO_ROOT, "pyproject.toml")
        if os.path.isfile(pyproject):
            with self.assertRaises(NotADirectoryError):
                scan_repo(pyproject)

    def test_valid_path_returns_list(self):
        result = scan_repo(DEMO)
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)


class TestRankHotspotsEdgeCases(unittest.TestCase):
    """rank_hotspots edge cases."""

    def test_empty_list_returns_empty(self):
        self.assertEqual(rank_hotspots([]), [])

    def test_top_zero_raises_value_error(self):
        files = scan_repo(DEMO)
        with self.assertRaises(ValueError):
            rank_hotspots(files, top=0)

    def test_top_negative_raises_value_error(self):
        files = scan_repo(DEMO)
        with self.assertRaises(ValueError):
            rank_hotspots(files, top=-1)

    def test_top_larger_than_files_returns_all(self):
        files = scan_repo(DEMO)
        result = rank_hotspots(files, top=9999)
        self.assertEqual(len(result), len(files))

    def test_single_file_gets_positive_score(self):
        """A single file is the only hotspot; score must be in (0, 100]."""
        f = FileInfo(
            path="solo.py", lang="python", lines=10, code_lines=8,
            complexity=3, defs=2,
        )
        result = rank_hotspots([f], top=1)
        self.assertEqual(len(result), 1)
        self.assertGreater(result[0].score, 0.0)
        self.assertLessEqual(result[0].score, 100.0)


class TestBuildMapEdgeCases(unittest.TestCase):
    """build_map on edge-case repos."""

    def test_empty_repo_no_crash(self):
        with tempfile.TemporaryDirectory() as d:
            rmap = build_map(d)
            self.assertEqual(rmap.files, [])
            self.assertEqual(rmap.hotspots, [])
            d_map = rmap.to_dict()
            self.assertEqual(d_map["summary"]["files"], 0)
            self.assertEqual(d_map["summary"]["code_lines"], 0)

    def test_to_dict_has_required_keys(self):
        rmap = build_map(DEMO)
        d = rmap.to_dict()
        for key in ("root", "summary", "packages", "hotspots", "files"):
            self.assertIn(key, d)

    def test_missing_dir_returns_exit_2(self):
        rc = main(["map", "/no/such/path_xyz_missing"])
        self.assertEqual(rc, 2)


class TestCLIHardeningPaths(unittest.TestCase):
    """CLI error paths added during hardening."""

    def test_top_zero_exits_nonzero(self):
        out = subprocess.run(
            [sys.executable, "-m", "codeglance", "hotspots", DEMO, "--top", "0"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(out.returncode, 0)

    def test_top_negative_exits_nonzero(self):
        out = subprocess.run(
            [sys.executable, "-m", "codeglance", "hotspots", DEMO, "--top", "-5"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(out.returncode, 0)

    def test_bad_path_stderr_message(self):
        out = subprocess.run(
            [sys.executable, "-m", "codeglance", "map", "/definitely/missing/path"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(out.returncode, 0)
        self.assertIn("codeglance", out.stderr)

    def test_deps_json_empty_repo(self):
        with tempfile.TemporaryDirectory() as d:
            out = subprocess.run(
                [sys.executable, "-m", "codeglance", "--format", "json", "deps", d],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
            )
            self.assertEqual(out.returncode, 0)
            edges = json.loads(out.stdout)
            self.assertIsInstance(edges, list)
            self.assertEqual(edges, [])

    def test_hotspots_json_empty_repo(self):
        with tempfile.TemporaryDirectory() as d:
            out = subprocess.run(
                [sys.executable, "-m", "codeglance", "--format", "json", "hotspots", d],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
            )
            self.assertEqual(out.returncode, 0)
            data = json.loads(out.stdout)
            self.assertEqual(data, [])


class TestMCPServerImport(unittest.TestCase):
    """mcp_server module must import cleanly (broken before hardening)."""

    def test_import_succeeds(self):
        from codeglance import mcp_server  # noqa: F401
        self.assertTrue(callable(mcp_server.serve))


if __name__ == "__main__":
    unittest.main()
