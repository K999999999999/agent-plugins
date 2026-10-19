"""Plugin metadata, shared Skill wiring, and repository CI contract checks."""

from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess
import sys
import unittest


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PLUGIN = PLUGIN_ROOT / "plugins/engineering-workflow"
CLI = WORKFLOW_PLUGIN / "tools/harness.py"


class HarnessPluginIntegrationTests(unittest.TestCase):
    def test_plugin_manifest_and_marketplace_source_remain_valid(self) -> None:
        manifest_path = WORKFLOW_PLUGIN / ".codex-plugin/plugin.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["name"], "engineering-workflow")
        self.assertRegex(manifest["version"], r"^\d+\.\d+\.\d+")
        self.assertTrue((WORKFLOW_PLUGIN / manifest["skills"].removeprefix("./")).is_dir())
        self.assertTrue((WORKFLOW_PLUGIN / "tools/harness.py").is_file())
        self.assertTrue((WORKFLOW_PLUGIN / "tools/harness_lib/state.py").is_file())
        self.assertFalse((PLUGIN_ROOT / "tools/harness.py").exists())
        self.assertIn("Harness", manifest["interface"]["longDescription"])

        marketplace = json.loads((PLUGIN_ROOT / ".agents/plugins/marketplace.json").read_text(encoding="utf-8"))
        entry = next(item for item in marketplace["plugins"] if item["name"] == "engineering-workflow")
        self.assertEqual(entry["source"]["path"], "./plugins/engineering-workflow")

    def test_all_stage_skills_link_to_one_shared_harness_contract(self) -> None:
        shared = PLUGIN_ROOT / "plugins/engineering-workflow/references/harness-integration.md"
        self.assertTrue(shared.is_file())
        skill_files = sorted((WORKFLOW_PLUGIN / "skills").glob("*/SKILL.md"))
        self.assertEqual(len(skill_files), 13)
        for skill in skill_files:
            with self.subTest(skill=skill.parent.name):
                text = skill.read_text(encoding="utf-8")
                self.assertIn("## Harness 工具协作", text)
                self.assertIn("../../references/harness-integration.md", text)
                resolved = (skill.parent / "../../references/harness-integration.md").resolve()
                self.assertEqual(resolved, shared.resolve())
        shared_text = shared.read_text(encoding="utf-8")
        self.assertNotRegex(shared_text, r"(?:[A-Za-z]:\\|/home/|/Users/)")
        self.assertIn("unavailable", shared_text)
        self.assertIn("diagnostic wait/resume", shared_text)
        self.assertIn("onboard apply", shared_text)

    def test_plugin_ci_runs_python311_standard_library_suite_without_cache_or_services(self) -> None:
        workflow = (PLUGIN_ROOT / ".github/workflows/harness-tests.yml").read_text(encoding="utf-8")
        self.assertIn("  push:", workflow)
        self.assertIn("  pull_request:", workflow)
        self.assertIn("  workflow_dispatch:", workflow)
        self.assertRegex(workflow, r"(?m)^permissions:\n  contents: read$")
        self.assertIn("timeout-minutes: 10", workflow)
        self.assertIn('version: "0.12.2"', workflow)
        self.assertIn("enable-cache: false", workflow)
        self.assertIn("uv python install 3.11", workflow)
        self.assertIn("uv run --no-project --python 3.11 python -m unittest discover -s tests -v", workflow)
        self.assertNotIn("actions/cache", workflow)
        self.assertNotIn("pull_request_target", workflow)
        action_refs = re.findall(r"(?m)^\s+uses:\s+[^@\s]+@([0-9a-f]{40})\b", workflow)
        self.assertEqual(len(action_refs), 2)
        self.assertNotIn("secrets.", workflow)

    def test_cli_exposes_lifecycle_and_harness_commands(self) -> None:
        result = subprocess.run(
            [sys.executable, str(CLI), "--help"], check=True, capture_output=True, text=True,
        )
        for command in (
            "state", "diff", "migrate", "cancel", "diagnostic", "closeout",
            "maintenance", "onboard",
        ):
            self.assertIn(command, result.stdout)


if __name__ == "__main__":
    unittest.main()
