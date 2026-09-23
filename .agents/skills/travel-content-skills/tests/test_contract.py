from __future__ import annotations

import copy
import importlib.util
import json
import sys
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = SKILL_ROOT / "scripts"
SAMPLE_PATH = SKILL_ROOT / "examples" / "sample-script.json"
sys.path.insert(0, str(SCRIPTS_DIR))

MODULE_PATH = SCRIPTS_DIR / "script_contract.py"
SPEC = importlib.util.spec_from_file_location("script_contract", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def sample_script() -> dict[str, object]:
    return json.loads(SAMPLE_PATH.read_text(encoding="utf-8"))


class ScriptContractTests(unittest.TestCase):
    def test_effective_char_count_ignores_punctuation(self):
        self.assertEqual(MODULE.effective_char_count("山河，2026！"), 6)

    def test_sample_script_passes(self):
        report = MODULE.validate_script(sample_script())
        self.assertEqual(report["status"], "passed")
        self.assertEqual(report["error_count"], 0)
        self.assertEqual(report["warning_count"], 0)

    def test_missing_location_is_error(self):
        script = copy.deepcopy(sample_script())
        script["narration"]["sections"][2]["text"] = "第二站去山林。"
        report = MODULE.validate_script(script)
        codes = {item["code"] for item in report["issues"]}
        self.assertIn("location-missing-from-copy", codes)

    def test_missing_tone_marker_is_error(self):
        script = copy.deepcopy(sample_script())
        script["narration"]["sections"][3]["text"] = "下午到龙井村，茶山顺着坡地展开。"
        report = MODULE.validate_script(script)
        codes = {item["code"] for item in report["issues"]}
        self.assertIn("tone-marker-missing-from-copy", codes)

    def test_assigned_duration_mismatch_is_error(self):
        script = copy.deepcopy(sample_script())
        script["narration"]["sections"][0]["target_seconds"] = 1
        report = MODULE.validate_script(script)
        codes = {item["code"] for item in report["issues"]}
        self.assertIn("assigned-duration-mismatch", codes)

    def test_duration_estimate_mismatch_is_error(self):
        script = copy.deepcopy(sample_script())
        script["project"]["duration_seconds"] = 180
        report = MODULE.validate_script(script)
        codes = {item["code"] for item in report["issues"]}
        self.assertIn("estimated-duration-mismatch", codes)


if __name__ == "__main__":
    unittest.main()
