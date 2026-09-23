from __future__ import annotations

import importlib.util
import json
import shutil
import sys
import unittest
import zipfile
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = SKILL_ROOT / "scripts"
SAMPLE_PATH = SKILL_ROOT / "examples" / "sample-script.json"
OUTPUT_DIR = SKILL_ROOT / "tests" / "_output"
sys.path.insert(0, str(SCRIPTS_DIR))

MODULE_PATH = SCRIPTS_DIR / "build_docx.py"
SPEC = importlib.util.spec_from_file_location("build_docx", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class BuildDocxTests(unittest.TestCase):
    def setUp(self):
        if OUTPUT_DIR.exists():
            shutil.rmtree(OUTPUT_DIR)
        OUTPUT_DIR.mkdir()

    def tearDown(self):
        if OUTPUT_DIR.exists():
            shutil.rmtree(OUTPUT_DIR)

    def test_builds_parseable_docx_with_required_content(self):
        script = json.loads(SAMPLE_PATH.read_text(encoding="utf-8"))

        output = OUTPUT_DIR / "杭州慢行.docx"
        MODULE.build_docx(script, output)

        self.assertEqual(MODULE.check_docx(output), [])
        with zipfile.ZipFile(output) as archive:
            document = archive.read("word/document.xml").decode("utf-8")

        self.assertIn("杭州慢行 旅游视频文案", document)
        self.assertIn("西湖", document)
        self.assertIn("灵隐寺", document)
        self.assertIn("龙井村", document)
        self.assertIn("温暖治愈", document)
        self.assertIn("完整配音文案", document)

    def test_invalid_contract_does_not_build_docx(self):
        script = json.loads(SAMPLE_PATH.read_text(encoding="utf-8"))
        script["project"]["locations"] = []

        output = OUTPUT_DIR / "invalid.docx"
        with self.assertRaises(ValueError):
            MODULE.build_docx(script, output)
        self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
