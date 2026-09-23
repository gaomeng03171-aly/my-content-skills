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

    def test_time_range_uses_start_and_end(self):
        self.assertEqual(
            MODULE.format_time_range(0, 12),
            "00:00-00:12",
        )
        self.assertEqual(
            MODULE.format_time_range(72, 90),
            "01:12-01:30",
        )

    def test_sample_script_passes(self):
        report = MODULE.validate_script(sample_script())
        self.assertEqual(report["status"], "passed")
        self.assertEqual(report["error_count"], 0)
        self.assertEqual(report["warning_count"], 0)
        self.assertEqual(
            report["metrics"]["segments"][0]["time_range"],
            "00:00-00:12",
        )

    def test_timeline_gap_is_error(self):
        script = copy.deepcopy(sample_script())
        script["segments"][2]["start_seconds"] = 37
        report = MODULE.validate_script(script)
        codes = {item["code"] for item in report["issues"]}
        self.assertIn("timeline-gap-or-overlap", codes)

    def test_audience_must_include_middle_aged_and_older(self):
        script = copy.deepcopy(sample_script())
        script["project"]["audience"] = "年轻观众"
        report = MODULE.validate_script(script)
        codes = {item["code"] for item in report["issues"]}
        self.assertIn("audience-out-of-scope", codes)

    def test_unverified_claim_is_error(self):
        script = copy.deepcopy(sample_script())
        script["claims"][0]["verification_status"] = "unverified"
        report = MODULE.validate_script(script)
        codes = {item["code"] for item in report["issues"]}
        self.assertIn("claim-not-verified", codes)

    def test_high_risk_claim_needs_two_evidence_items(self):
        script = copy.deepcopy(sample_script())
        script["claims"][0]["risk_level"] = "high"
        script["claims"][0]["category"] = "historical"
        report = MODULE.validate_script(script)
        codes = {item["code"] for item in report["issues"]}
        self.assertIn("claim-high-risk-evidence-insufficient", codes)

    def test_fact_marker_requires_claim_link(self):
        script = copy.deepcopy(sample_script())
        script["segments"][2]["claim_ids"] = []
        report = MODULE.validate_script(script)
        codes = {item["code"] for item in report["issues"]}
        self.assertIn("fact-marker-without-claim", codes)

    def test_personal_medical_advice_is_error(self):
        script = copy.deepcopy(sample_script())
        script["segments"][3]["text"] += "这段内容可以保证治好。"
        report = MODULE.validate_script(script)
        codes = {item["code"] for item in report["issues"]}
        self.assertIn("forbidden-medical-legal-advice", codes)


if __name__ == "__main__":
    unittest.main()
