"""Smoke + behavior tests for CODEGLANCE. No network, stdlib only."""
import json
import os
import subprocess
import sys
import unittest

import codeglance
from codeglance import build_map, rank_hotspots, scan_repo, TOOL_NAME, TOOL_VERSION
from codeglance.cli import main

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEMO = os.path.join(REPO_ROOT, "demos", "01-basic")


class TestExports(unittest.TestCase):
    def test_metadata(self):
        self.assertEqual(TOOL_NAME, "codeglance")
        self.assertTrue(TOOL_VERSION)
        for name in ("scan_repo", "build_map", "rank_hotspots", "RepoMap", "FileInfo"):
            self.assertTrue(hasattr(codeglance, name))


class TestEngine(unittest.TestCase):
    def test_scan_finds_demo_files(self):
        files = scan_repo(DEMO)
        paths = {f.path for f in files}
        self.assertIn("sample_pkg/service.py", paths)
        self.assertIn("sample_pkg/config.py", paths)
        self.assertTrue(all(f.lines > 0 for f in files))

    def test_dependency_resolution(self):
        rmap = build_map(DEMO)
        by_path = {f.path: f for f in rmap.files}
        service = by_path["sample_pkg/service.py"]
        # service imports models and config
        self.assertIn("sample_pkg/models.py", service.deps)
        self.assertIn("sample_pkg/config.py", service.deps)
        # config is a leaf with no internal deps but several dependents
        config = by_path["sample_pkg/config.py"]
        self.assertEqual(config.deps, [])
        self.assertTrue(len(config.dependents) >= 2)

    def test_service_is_top_hotspot(self):
        rmap = build_map(DEMO)
        top_paths = [f.path for f in rmap.hotspots[:2]]
        self.assertIn("sample_pkg/service.py", top_paths)

    def test_complexity_leaf_vs_branchy(self):
        rmap = build_map(DEMO)
        by_path = {f.path: f for f in rmap.files}
        self.assertGreater(
            by_path["sample_pkg/service.py"].complexity,
            by_path["sample_pkg/config.py"].complexity,
        )

    def test_missing_root_raises(self):
        with self.assertRaises(NotADirectoryError):
            scan_repo(os.path.join(DEMO, "does-not-exist"))

    def test_empty_hotspots(self):
        self.assertEqual(rank_hotspots([]), [])


class TestCLI(unittest.TestCase):
    def test_map_json_exit_zero(self):
        rc = main(["--format", "json", "map", DEMO])
        self.assertEqual(rc, 0)

    def test_hotspots_json_structure(self):
        # Capture via subprocess to validate real JSON on stdout.
        out = subprocess.run(
            [sys.executable, "-m", "codeglance", "--format", "json",
             "hotspots", DEMO, "--top", "3"],
            cwd=REPO_ROOT, capture_output=True, text=True,
        )
        self.assertEqual(out.returncode, 0, out.stderr)
        data = json.loads(out.stdout)
        self.assertTrue(isinstance(data, list) and len(data) <= 3)
        self.assertIn("score", data[0])
        self.assertIn("fan_in", data[0])

    def test_deps_table_exit_zero(self):
        rc = main(["deps", DEMO])
        self.assertEqual(rc, 0)

    def test_nonzero_on_bad_path(self):
        rc = main(["map", os.path.join(DEMO, "nope-missing")])
        self.assertNotEqual(rc, 0)

    def test_version(self):
        with self.assertRaises(SystemExit) as ctx:
            main(["--version"])
        self.assertEqual(ctx.exception.code, 0)


if __name__ == "__main__":
    unittest.main()
