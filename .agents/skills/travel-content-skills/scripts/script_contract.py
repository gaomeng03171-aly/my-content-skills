#!/usr/bin/env python3
"""Shared validation helpers for the travel video copy contract."""

from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree


SLOW_CPM = 210
FAST_CPM = 260
DEFAULT_CPM = 235
SENTENCE_RE = re.compile(r"[^。！？!?…]+(?:[。！？!?]+|…{2})?")
HYPE_PHRASES = (
    "最美",
    "必去",
    "世界第一",
    "治愈一生",
    "来了就不想走",
    "百分之百",
)
FILLER_PHRASES = (
    "综上所述",
    "值得一提的是",
    "从某种意义上讲",
    "其实吧",
    "然后呢",
)
DOCX_REQUIRED_PARTS = {
    "[Content_Types].xml",
    "_rels/.rels",
    "word/document.xml",
    "word/styles.xml",
    "docProps/core.xml",
    "docProps/app.xml",
}


def effective_char_count(text: str) -> int:
    """Count CJK characters and alphanumerics, ignoring punctuation and spacing."""
    return sum(
        1
        for char in text
        if char.isalnum() or "\u3400" <= char <= "\u9fff"
    )


def load_json(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("script JSON root must be an object")
    return payload


def _mapping(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}


def _items(value: object) -> list[object]:
    return value if isinstance(value, list) else []


def _text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _issue(
    issues: list[dict[str, str]],
    level: str,
    code: str,
    message: str,
    path: str,
) -> None:
    issues.append(
        {
            "level": level,
            "code": code,
            "message": message,
            "path": path,
        }
    )


def narration_text(script: dict[str, object]) -> str:
    narration = _mapping(script.get("narration"))
    sections = _items(narration.get("sections"))
    return "\n".join(
        _text(_mapping(section).get("text"))
        for section in sections
        if _text(_mapping(section).get("text"))
    )


def estimate_seconds(char_count: int, cpm: int) -> float:
    if cpm <= 0:
        raise ValueError("cpm must be greater than zero")
    return char_count / cpm * 60


def validate_script(script: dict[str, object]) -> dict[str, object]:
    """Return a deterministic quality report for a travel script contract."""
    issues: list[dict[str, str]] = []

    if not isinstance(script, dict):
        _issue(issues, "error", "root-type", "JSON 根节点必须是对象", "$")
        return {
            "status": "failed",
            "error_count": 1,
            "warning_count": 0,
            "issues": issues,
        }

    if script.get("schema_version") != 1:
        _issue(
            issues,
            "error",
            "schema-version",
            "schema_version 必须为 1",
            "$.schema_version",
        )

    project = _mapping(script.get("project"))
    project_name = _text(project.get("name"))
    if not project_name:
        _issue(issues, "error", "project-name", "缺少项目名称", "$.project.name")

    raw_locations = _items(project.get("locations"))
    locations: list[str] = []
    for index, value in enumerate(raw_locations):
        location = _text(value)
        if not location:
            _issue(
                issues,
                "error",
                "location-empty",
                "地点不能为空",
                f"$.project.locations[{index}]",
            )
            continue
        if location in locations:
            _issue(
                issues,
                "error",
                "location-duplicate",
                f"地点重复：{location}",
                f"$.project.locations[{index}]",
            )
        locations.append(location)
    if not locations:
        _issue(
            issues,
            "error",
            "locations-missing",
            "至少需要一个旅游地点",
            "$.project.locations",
        )

    tone = _text(project.get("tone"))
    if not tone:
        _issue(issues, "error", "tone-missing", "缺少情感基调", "$.project.tone")
    elif len(tone) > 20:
        _issue(
            issues,
            "warning",
            "tone-long",
            "情感基调较长，确认其是否为单一主基调",
            "$.project.tone",
        )

    duration_value = project.get("duration_seconds")
    duration = (
        float(duration_value)
        if isinstance(duration_value, (int, float))
        and not isinstance(duration_value, bool)
        else 0.0
    )
    if duration < 15:
        _issue(
            issues,
            "error",
            "duration-invalid",
            "视频总时长必须至少为 15 秒",
            "$.project.duration_seconds",
        )

    strategy = _mapping(script.get("strategy"))
    for key, label in (
        ("core_theme", "核心主题"),
        ("opening_angle", "开场设计"),
        ("closing_idea", "收束设计"),
    ):
        if not _text(strategy.get(key)):
            _issue(
                issues,
                "error",
                f"{key}-missing",
                f"缺少{label}",
                f"$.strategy.{key}",
            )

    role_entries = _items(strategy.get("location_roles"))
    role_map: dict[str, str] = {}
    for index, entry in enumerate(role_entries):
        item = _mapping(entry)
        location = _text(item.get("location"))
        role = _text(item.get("role"))
        if not location or not role:
            _issue(
                issues,
                "error",
                "location-role-invalid",
                "地点职责必须同时包含 location 和 role",
                f"$.strategy.location_roles[{index}]",
            )
            continue
        if location in role_map:
            _issue(
                issues,
                "error",
                "location-role-duplicate",
                f"地点职责重复：{location}",
                f"$.strategy.location_roles[{index}]",
            )
        role_map[location] = role

    for location in locations:
        if location not in role_map:
            _issue(
                issues,
                "error",
                "location-role-missing",
                f"缺少地点职责：{location}",
                "$.strategy.location_roles",
            )
    for location in role_map:
        if location not in locations:
            _issue(
                issues,
                "error",
                "location-role-unknown",
                f"地点职责包含未声明的项目地点：{location}",
                "$.strategy.location_roles",
            )

    raw_tone_markers = _items(strategy.get("tone_markers"))
    tone_markers: list[str] = []
    for index, value in enumerate(raw_tone_markers):
        marker = _text(value)
        if not marker:
            _issue(
                issues,
                "error",
                "tone-marker-empty",
                "情感标记不能为空",
                f"$.strategy.tone_markers[{index}]",
            )
            continue
        if marker in tone_markers:
            _issue(
                issues,
                "error",
                "tone-marker-duplicate",
                f"情感标记重复：{marker}",
                f"$.strategy.tone_markers[{index}]",
            )
        tone_markers.append(marker)
    if not 2 <= len(tone_markers) <= 5:
        _issue(
            issues,
            "error",
            "tone-marker-count",
            "情感标记数量必须为 2 至 5 个",
            "$.strategy.tone_markers",
        )

    narration = _mapping(script.get("narration"))
    sections = _items(narration.get("sections"))
    if not sections:
        _issue(
            issues,
            "error",
            "sections-missing",
            "至少需要一个正文段落",
            "$.narration.sections",
        )

    assigned_seconds = 0.0
    section_reports: list[dict[str, object]] = []
    for index, entry in enumerate(sections):
        section = _mapping(entry)
        name = _text(section.get("name"))
        text = _text(section.get("text"))
        section_locations = [
            _text(value) for value in _items(section.get("locations")) if _text(value)
        ]
        target_value = section.get("target_seconds")
        target_seconds = (
            float(target_value)
            if isinstance(target_value, (int, float))
            and not isinstance(target_value, bool)
            else 0.0
        )

        if not name:
            _issue(
                issues,
                "error",
                "section-name-missing",
                "正文段落缺少名称",
                f"$.narration.sections[{index}].name",
            )
        if not text:
            _issue(
                issues,
                "error",
                "section-text-missing",
                "正文段落缺少 text",
                f"$.narration.sections[{index}].text",
            )
        if target_seconds <= 0:
            _issue(
                issues,
                "error",
                "section-duration-invalid",
                "段落 target_seconds 必须大于 0",
                f"$.narration.sections[{index}].target_seconds",
            )
        if not section_locations:
            _issue(
                issues,
                "error",
                "section-locations-missing",
                "正文段落至少关联一个地点",
                f"$.narration.sections[{index}].locations",
            )
        for location in section_locations:
            if location not in locations:
                _issue(
                    issues,
                    "error",
                    "section-location-unknown",
                    f"段落引用了未声明地点：{location}",
                    f"$.narration.sections[{index}].locations",
                )

        assigned_seconds += max(target_seconds, 0.0)
        section_reports.append(
            {
                "name": name,
                "target_seconds": round(target_seconds, 2),
                "effective_char_count": effective_char_count(text),
            }
        )

    full_text = narration_text(script)
    for location in locations:
        if location not in full_text:
            _issue(
                issues,
                "error",
                "location-missing-from-copy",
                f"地点未进入完整正文：{location}",
                "$.narration.sections",
            )
    for marker in tone_markers:
        if marker not in full_text:
            _issue(
                issues,
                "error",
                "tone-marker-missing-from-copy",
                f"情感标记未进入正文：{marker}",
                "$.narration.sections",
            )

    titles = [_text(value) for value in _items(script.get("titles")) if _text(value)]
    if len(titles) < 3:
        _issue(
            issues,
            "error",
            "titles-insufficient",
            "至少提供 3 条标题方案",
            "$.titles",
        )

    delivery = _mapping(script.get("delivery"))
    version = _text(delivery.get("version"))
    date = _text(delivery.get("date"))
    if not version:
        _issue(
            issues,
            "error",
            "version-missing",
            "缺少交付版本",
            "$.delivery.version",
        )
    if not date:
        _issue(
            issues,
            "error",
            "date-missing",
            "缺少交付日期",
            "$.delivery.date",
        )

    duration_tolerance = max(5.0, duration * 0.10)
    if duration > 0 and abs(assigned_seconds - duration) > duration_tolerance:
        _issue(
            issues,
            "error",
            "assigned-duration-mismatch",
            (
                f"段落目标时长合计 {assigned_seconds:.1f} 秒，与总时长 "
                f"{duration:.1f} 秒的偏差超过 {duration_tolerance:.1f} 秒"
            ),
            "$.narration.sections",
        )

    char_count = effective_char_count(full_text)
    estimated_min = estimate_seconds(char_count, FAST_CPM)
    estimated_max = estimate_seconds(char_count, SLOW_CPM)
    target_min = max(0.0, duration - duration_tolerance)
    target_max = duration + duration_tolerance
    duration_overlap = (
        max(estimated_min, target_min) <= min(estimated_max, target_max)
        if duration > 0
        else False
    )
    recommended_min = max(0, round(target_min / 60 * SLOW_CPM))
    recommended_max = max(0, round(target_max / 60 * FAST_CPM))
    if duration > 0 and not duration_overlap:
        _issue(
            issues,
            "error",
            "estimated-duration-mismatch",
            (
                f"有效字符 {char_count}，估算 {estimated_min:.1f} 至 "
                f"{estimated_max:.1f} 秒，与目标区间 {target_min:.1f} 至 "
                f"{target_max:.1f} 秒不重叠；建议字符数约 "
                f"{recommended_min} 至 {recommended_max}"
            ),
            "$.narration.sections",
        )

    for sentence in SENTENCE_RE.findall(full_text):
        sentence = sentence.strip()
        count = effective_char_count(sentence)
        if count > 45:
            _issue(
                issues,
                "warning",
                "long-sentence",
                f"发现 {count} 个有效字符的长句，建议检查听辨负担",
                "$.narration.sections",
            )
    for phrase in HYPE_PHRASES:
        if phrase in full_text:
            _issue(
                issues,
                "warning",
                "hype-expression",
                f"发现空泛夸张表达：{phrase}",
                "$.narration.sections",
            )
    for phrase in FILLER_PHRASES:
        if phrase in full_text:
            _issue(
                issues,
                "warning",
                "filler-expression",
                f"发现模板套话：{phrase}",
                "$.narration.sections",
            )

    errors = sum(item["level"] == "error" for item in issues)
    warnings = sum(item["level"] == "warning" for item in issues)
    status = "failed" if errors else ("review" if warnings else "passed")

    return {
        "status": status,
        "error_count": errors,
        "warning_count": warnings,
        "project": {
            "name": project_name,
            "locations": locations,
            "tone": tone,
            "duration_seconds": round(duration, 2),
        },
        "metrics": {
            "effective_char_count": char_count,
            "assigned_seconds": round(assigned_seconds, 2),
            "estimated_seconds": {
                "minimum_at_260_cpm": round(estimated_min, 2),
                "maximum_at_210_cpm": round(estimated_max, 2),
                "recommended_at_235_cpm": round(
                    estimate_seconds(char_count, DEFAULT_CPM),
                    2,
                ),
            },
            "recommended_effective_chars": {
                "minimum": recommended_min,
                "maximum": recommended_max,
            },
            "sections": section_reports,
        },
        "issues": issues,
    }


def check_docx(path: Path) -> list[str]:
    """Check a DOCX package for required parts and parseable core XML."""
    errors: list[str] = []
    if not path.is_file():
        return [f"DOCX 不存在：{path}"]

    try:
        with zipfile.ZipFile(path) as archive:
            names = set(archive.namelist())
            for part in sorted(DOCX_REQUIRED_PARTS):
                if part not in names:
                    errors.append(f"缺少 DOCX 部件：{part}")
            for part in sorted(DOCX_REQUIRED_PARTS):
                if part not in names or not part.endswith(".xml") and not part.endswith(".rels"):
                    continue
                try:
                    ElementTree.fromstring(archive.read(part))
                except ElementTree.ParseError as exc:
                    errors.append(f"{part} XML 无法解析：{exc}")
    except (OSError, zipfile.BadZipFile) as exc:
        errors.append(f"无法读取 DOCX：{exc}")

    return errors
