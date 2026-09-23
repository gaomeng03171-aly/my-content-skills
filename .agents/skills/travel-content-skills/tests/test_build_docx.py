from __future__ import annotations

import importlib.util
import io
import json
import shutil
import sys
import unittest
import zipfile
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = SKILL_ROOT / "scripts"
SAMPLE_PATH = SKILL_ROOT / "examples" / "sample-script.json"
REPO_ROOT = SKILL_ROOT.parents[2]
OUTPUT_DIR = REPO_ROOT / ".travel-content-skill-test-output"
PACKAGE_PATH = REPO_ROOT / "西湖慢行：茶香与山林之间_交付包.zip"
sys.path.insert(0, str(SCRIPTS_DIR))

MODULE_PATH = SCRIPTS_DIR / "build_package.py"
SPEC = importlib.util.spec_from_file_location("build_package", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class BuildPackageTests(unittest.TestCase):
    def setUp(self):
        if OUTPUT_DIR.exists():
            shutil.rmtree(OUTPUT_DIR)
        if PACKAGE_PATH.exists():
            PACKAGE_PATH.unlink()
        OUTPUT_DIR.mkdir()

    def tearDown(self):
        if OUTPUT_DIR.exists():
            shutil.rmtree(OUTPUT_DIR)
        if PACKAGE_PATH.exists():
            PACKAGE_PATH.unlink()

    def test_builds_three_part_package_with_timeline_first(self):
        script = json.loads(SAMPLE_PATH.read_text(encoding="utf-8"))

        result = MODULE.build_package(script, OUTPUT_DIR)
        package_path = Path(result["package_path"])

        self.assertEqual(MODULE.check_package(package_path), [])
        with zipfile.ZipFile(package_path) as archive:
            self.assertEqual(
                set(archive.namelist()),
                set(MODULE.PACKAGE_FILES),
            )
            with zipfile.ZipFile(
                io.BytesIO(archive.read(MODULE.READABLE_NAME))
            ) as readable_docx:
                readable = readable_docx.read("word/document.xml").decode("utf-8")
            with zipfile.ZipFile(
                io.BytesIO(archive.read(MODULE.REVIEW_NAME))
            ) as review_docx:
                review = review_docx.read("word/document.xml").decode("utf-8")
            evidence = archive.read(MODULE.EVIDENCE_NAME).decode("utf-8-sig")

        expected_range = "A：00:00-00:12"
        self.assertIn(expected_range, readable)
        self.assertIn(expected_range, review)
        self.assertLess(
            readable.index("视频文案顺序与占用时间表"),
            readable.index(
                "可朗读正文",
                readable.index("视频文案顺序与占用时间表"),
            ),
        )
        self.assertLess(
            review.index("视频文案顺序与占用时间表"),
            review.index("项目概览"),
        )
        self.assertIn("证据编号", evidence)
        self.assertIn("灵隐寺官网", evidence)

    def test_invalid_contract_does_not_build_package(self):
        script = json.loads(SAMPLE_PATH.read_text(encoding="utf-8"))
        script["segments"][2]["start_seconds"] = 37

        with self.assertRaises(ValueError):
            MODULE.build_package(script, OUTPUT_DIR)
        self.assertEqual(list(OUTPUT_DIR.glob("*.docx")), [])
        self.assertEqual(list(OUTPUT_DIR.glob("*.csv")), [])
        self.assertFalse(PACKAGE_PATH.exists())


if __name__ == "__main__":
    unittest.main()
