#!/usr/bin/env python3
"""Validate a middle-aged and older audience narration package contract."""

from __future__ import annotations

import json
import re
import zipfile
from datetime import date
from pathlib import Path
from xml.etree import ElementTree


SCHEMA_VERSION = 2
SLOW_CPM = 170
FAST_CPM = 210
DEFAULT_CPM = 190
MAX_SENTENCE_ERROR = 45
MAX_SENTENCE_REVIEW = 35
TIME_TOLERANCE = 0.01
SENTENCE_RE = re.compile(r"[^。！？!?…]+(?:[。！？!?]+|…{2})?")
SEGMENT_ID_RE = re.compile(r"^[A-Z][A-Z0-9_-]{0,7}$")
CLAIM_ID_RE = re.compile(r"^C[0-9]+$")
EVIDENCE_ID_RE = re.compile(r"^E[0-9]+$")
FACT_MARKER_RE = re.compile(
    r"(?:公元|[0-9]{2,4}年|世纪|世界遗产|国家级|省级|市级|"
    r"建于|始建|发源|位于|海拔|公里|统计|研究显示|政策|法规|"
    r"法律规定|药物|剂量|治疗|诊断|安全风险)"
)
HYPE_PHRASES = (
    "最美",
    "必去",
    "世界第一",
    "治愈一生",
    "来了就不想走",
    "百分之百",
    "绝对有效",
)
FILLER_PHRASES = (
    "综上所述",
    "值得一提的是",
    "从某种意义上讲",
    "其实吧",
    "然后呢",
)
FORBIDDEN_ADVICE_RE = re.compile(
    r"(?:自行停药|马上停药|停止用药|自行加药|自行减药|具体剂量|"
    r"包治|根治|保证治好|替代就医|无需就医|代替医生|"
    r"保证胜诉|一定能赢|规避法律|不用请律师)"
)
DOMAINS = {"history_culture", "geography_travel", "life_skill"}
PROJECT_TYPES = {"single", "series"}
RISK_LEVELS = {"low", "medium", "high"}
CLAIM_CATEGORIES = {
    "historical",
    "cultural",
    "geographic",
    "scientific",
    "life_practice",
    "safety",
    "medical",
    "legal",
    "other",
}
VERIFICATION_STATUSES = {"verified", "unverified", "disputed"}
EVIDENCE_STATUSES = {"verified", "partial", "unverified", "disputed"}
RELIABILITY_LEVELS = {"high", "medium", "low"}
SOURCE_TYPES = {
    "official",
    "academic",
    "primary",
    "professional",
    "authoritative_media",
    "user_material",
}
AUTHORITATIVE_SOURCE_TYPES = {
    "official",
    "academic",
    "primary",
    "professional",
}
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


def estimate_seconds(char_count: int, cpm: int = DEFAULT_CPM) -> float:
    if cpm <= 0:
        raise ValueError("cpm must be greater than zero")
    return char_count / cpm * 60


def format_timecode(seconds: float) -> str:
    """Format a non-negative duration as mm:ss, or hh:mm:ss past one hour."""
    total = max(0, int(round(seconds)))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def format_time_range(start_seconds: float, end_seconds: float) -> str:
    return f"{format_timecode(start_seconds)}-{format_timecode(end_seconds)}"


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


def _number(value: object) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None


def _unique_texts(value: object) -> list[str]:
    values: list[str] = []
    for item in _items(value):
        text = _text(item)
        if text and text not in values:
            values.append(text)
    return values


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


def _valid_iso_date(value: str) -> bool:
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def narration_text(script: dict[str, object]) -> str:
    return "\n".join(
        _text(_mapping(segment).get("text"))
        for segment in _items(script.get("segments"))
        if _text(_mapping(segment).get("text"))
    )


def _ranges_overlap(
    first_start: float,
    first_end: float,
    second_start: float,
    second_end: float,
) -> bool:
    return max(first_start, second_start) <= min(first_end, second_end)


def validate_script(script: dict[str, object]) -> dict[str, object]:
    """Return a deterministic quality report for the narration contract."""
    issues: list[dict[str, str]] = []

    if not isinstance(script, dict):
        _issue(issues, "error", "root-type", "JSON 根节点必须是对象", "$")
        return {
            "status": "failed",
            "error_count": 1,
            "warning_count": 0,
            "issues": issues,
        }

    if script.get("schema_version") != SCHEMA_VERSION:
        _issue(
            issues,
            "error",
            "schema-version",
            f"schema_version 必须为 {SCHEMA_VERSION}",
            "$.schema_version",
        )

    project = _mapping(script.get("project"))
    project_name = _text(project.get("name"))
    project_domain = _text(project.get("domain"))
    project_type = _text(project.get("project_type"))
    topic = _text(project.get("topic"))
    audience = _text(project.get("audience"))
    tone = _text(project.get("tone"))
    platform = _text(project.get("platform"))
    duration_value = project.get("duration_seconds")
    duration = _number(duration_value) or 0.0

    if not project_name:
        _issue(issues, "error", "project-name", "缺少项目名称", "$.project.name")
    if project_domain not in DOMAINS:
        _issue(
            issues,
            "error",
            "domain-invalid",
            "domain 必须是 history_culture、geography_travel 或 life_skill",
            "$.project.domain",
        )
    if project_type not in PROJECT_TYPES:
        _issue(
            issues,
            "error",
            "project-type-invalid",
            "project_type 必须是 single 或 series",
            "$.project.project_type",
        )
    if not topic:
        _issue(issues, "error", "topic-missing", "缺少本集核心主题", "$.project.topic")
    if not audience:
        _issue(
            issues,
            "error",
            "audience-missing",
            "缺少目标受众；本技能默认并优先使用“中老年受众”",
            "$.project.audience",
        )
    elif "中老年" not in audience:
        _issue(
            issues,
            "error",
            "audience-out-of-scope",
            "本技能的正式质量门槛面向中老年受众，audience 必须明确包含“中老年”",
            "$.project.audience",
        )
    if duration < 15:
        _issue(
            issues,
            "error",
            "duration-invalid",
            "视频总时长必须至少为 15 秒",
            "$.project.duration_seconds",
        )

    series_info = _mapping(project.get("series"))
    if project_type == "series":
        for key, label in (
            ("series_title", "系列名称"),
            ("episode_title", "本集名称"),
            ("arc_role", "本集承上启下职责"),
        ):
            if not _text(series_info.get(key)):
                _issue(
                    issues,
                    "error",
                    f"series-{key.replace('_', '-')}-missing",
                    f"系列项目缺少{label}",
                    f"$.project.series.{key}",
                )
        episode_number = _number(series_info.get("episode_number"))
        total_episodes = _number(series_info.get("total_episodes"))
        if episode_number is None or episode_number < 1:
            _issue(
                issues,
                "error",
                "series-episode-number-invalid",
                "系列项目必须提供有效的 episode_number",
                "$.project.series.episode_number",
            )
        if total_episodes is None or total_episodes < 1:
            _issue(
                issues,
                "error",
                "series-total-invalid",
                "系列项目必须提供有效的 total_episodes",
                "$.project.series.total_episodes",
            )
        if (
            episode_number is not None
            and total_episodes is not None
            and episode_number > total_episodes
        ):
            _issue(
                issues,
                "error",
                "series-episode-overflow",
                "episode_number 不能大于 total_episodes",
                "$.project.series",
            )

    strategy = _mapping(script.get("strategy"))
    for key, label in (
        ("core_theme", "核心主题"),
        ("opening_angle", "进入设计"),
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

    content_roles = _items(strategy.get("content_roles"))
    role_names: list[str] = []
    for index, entry in enumerate(content_roles):
        item = _mapping(entry)
        name = _text(item.get("name"))
        role = _text(item.get("role"))
        if not name or not role:
            _issue(
                issues,
                "error",
                "content-role-invalid",
                "内容职责必须同时包含 name 和 role",
                f"$.strategy.content_roles[{index}]",
            )
            continue
        if name in role_names:
            _issue(
                issues,
                "error",
                "content-role-duplicate",
                f"内容职责重复：{name}",
                f"$.strategy.content_roles[{index}]",
            )
        role_names.append(name)
    if not role_names:
        _issue(
            issues,
            "error",
            "content-roles-missing",
            "至少需要一条内容职责",
            "$.strategy.content_roles",
        )

    adaptations = _unique_texts(strategy.get("audience_adaptations"))
    if len(adaptations) < 2:
        _issue(
            issues,
            "error",
            "audience-adaptations-insufficient",
            "至少提供两条面向中老年受众的可执行适配说明",
            "$.strategy.audience_adaptations",
        )

    tone_markers = _unique_texts(strategy.get("tone_markers"))
    if not 2 <= len(tone_markers) <= 5:
        _issue(
            issues,
            "error",
            "tone-marker-count",
            "情感或表达标记数量必须为 2 至 5 个",
            "$.strategy.tone_markers",
        )

    segments = _items(script.get("segments"))
    segment_map: dict[str, dict[str, object]] = {}
    segment_claim_ids: dict[str, list[str]] = {}
    segment_reports: list[dict[str, object]] = []
    expected_start = 0.0
    final_end = 0.0
    for index, entry in enumerate(segments):
        segment = _mapping(entry)
        segment_id = _text(segment.get("id"))
        title = _text(segment.get("title"))
        text = _text(segment.get("text"))
        reading_notes = _text(segment.get("reading_notes"))
        start = _number(segment.get("start_seconds"))
        end = _number(segment.get("end_seconds"))
        claim_ids = _unique_texts(segment.get("claim_ids"))
        path = f"$.segments[{index}]"

        if not segment_id or not SEGMENT_ID_RE.fullmatch(segment_id):
            _issue(
                issues,
                "error",
                "segment-id-invalid",
                "段号必须是 A、B、C 或类似的 1 至 8 位大写编号",
                f"{path}.id",
            )
        elif segment_id in segment_map:
            _issue(
                issues,
                "error",
                "segment-id-duplicate",
                f"段号重复：{segment_id}",
                f"{path}.id",
            )
        else:
            segment_map[segment_id] = segment
        segment_claim_ids[segment_id] = claim_ids

        if not title:
            _issue(issues, "error", "segment-title-missing", "段落缺少标题", f"{path}.title")
        if not text:
            _issue(issues, "error", "segment-text-missing", "段落缺少可朗读正文", f"{path}.text")
        if start is None:
            _issue(
                issues,
                "error",
                "segment-start-missing",
                "段落缺少 start_seconds",
                f"{path}.start_seconds",
            )
        if end is None:
            _issue(
                issues,
                "error",
                "segment-end-missing",
                "段落缺少 end_seconds",
                f"{path}.end_seconds",
            )

        actual_start = start if start is not None else expected_start
        actual_end = end if end is not None else actual_start
        if end is not None and start is not None and end <= start:
            _issue(
                issues,
                "error",
                "segment-time-invalid",
                "段落 end_seconds 必须大于 start_seconds",
                f"{path}.end_seconds",
            )
        if index == 0 and start is not None and abs(start) > TIME_TOLERANCE:
            _issue(
                issues,
                "error",
                "timeline-must-start-at-zero",
                "时间轴必须从 00:00 开始",
                f"{path}.start_seconds",
            )
        if start is not None and abs(start - expected_start) > TIME_TOLERANCE:
            _issue(
                issues,
                "error",
                "timeline-gap-or-overlap",
                (
                    f"段 {segment_id or index + 1} 应从 "
                    f"{format_timecode(expected_start)} 开始，当前为 "
                    f"{format_timecode(start)}；时间轴不得留空隙或重叠"
                ),
                f"{path}.start_seconds",
            )
        if end is not None and duration > 0 and end > duration + TIME_TOLERANCE:
            _issue(
                issues,
                "error",
                "segment-past-duration",
                "段落结束时间超过项目总时长",
                f"{path}.end_seconds",
            )

        char_count = effective_char_count(text)
        estimated_min = estimate_seconds(char_count, FAST_CPM)
        estimated_max = estimate_seconds(char_count, SLOW_CPM)
        allocated_seconds = max(0.0, actual_end - actual_start)
        if (
            start is not None
            and end is not None
            and end > start
            and not _ranges_overlap(
                estimated_min,
                estimated_max,
                0.0,
                allocated_seconds,
            )
        ):
            _issue(
                issues,
                "error",
                "segment-reading-duration-mismatch",
                (
                    f"段 {segment_id or index + 1} 有效字符 {char_count}，"
                    f"估算 {estimated_min:.1f} 至 {estimated_max:.1f} 秒，"
                    f"与 {format_time_range(start, end)} 不重叠"
                ),
                f"{path}.text",
            )

        for sentence in SENTENCE_RE.findall(text):
            sentence = sentence.strip()
            sentence_count = effective_char_count(sentence)
            if sentence_count > MAX_SENTENCE_ERROR:
                _issue(
                    issues,
                    "error",
                    "sentence-too-long",
                    f"段 {segment_id or index + 1} 出现 {sentence_count} 个有效字符的句子",
                    f"{path}.text",
                )
            elif sentence_count > MAX_SENTENCE_REVIEW:
                _issue(
                    issues,
                    "warning",
                    "long-sentence-review",
                    f"段 {segment_id or index + 1} 出现 {sentence_count} 个有效字符的句子，建议复核听辨负担",
                    f"{path}.text",
                )
        if FACT_MARKER_RE.search(text) and not claim_ids:
            _issue(
                issues,
                "error",
                "fact-marker-without-claim",
                f"段 {segment_id or index + 1} 含事实性表述，但未关联 claim_ids",
                f"{path}.claim_ids",
            )

        segment_reports.append(
            {
                "id": segment_id,
                "title": title,
                "time_range": (
                    format_time_range(start, end)
                    if start is not None and end is not None
                    else ""
                ),
                "start_seconds": round(actual_start, 2),
                "end_seconds": round(actual_end, 2),
                "allocated_seconds": round(allocated_seconds, 2),
                "effective_char_count": char_count,
                "estimated_minimum_seconds": round(estimated_min, 2),
                "estimated_maximum_seconds": round(estimated_max, 2),
                "claim_ids": claim_ids,
                "reading_notes": reading_notes,
            }
        )
        expected_start = actual_end
        final_end = actual_end

    if not segments:
        _issue(
            issues,
            "error",
            "segments-missing",
            "至少需要两个按顺序排列的段落",
            "$.segments",
        )
    if duration > 0 and abs(final_end - duration) > TIME_TOLERANCE:
        _issue(
            issues,
            "error",
            "timeline-duration-mismatch",
            (
                f"时间轴结束于 {format_timecode(final_end)}，项目总时长为 "
                f"{format_timecode(duration)}"
            ),
            "$.segments",
        )

    claims = _items(script.get("claims"))
    claim_map: dict[str, dict[str, object]] = {}
    evidence_usage: dict[str, list[str]] = {}
    for index, entry in enumerate(claims):
        claim = _mapping(entry)
        claim_id = _text(claim.get("id"))
        statement = _text(claim.get("statement"))
        segment_ids = _unique_texts(claim.get("segment_ids"))
        evidence_ids = _unique_texts(claim.get("evidence_ids"))
        risk_level = _text(claim.get("risk_level"))
        category = _text(claim.get("category"))
        verification_status = _text(claim.get("verification_status"))
        path = f"$.claims[{index}]"

        if not claim_id or not CLAIM_ID_RE.fullmatch(claim_id):
            _issue(
                issues,
                "error",
                "claim-id-invalid",
                "事实编号必须使用 C1、C2 一类格式",
                f"{path}.id",
            )
        elif claim_id in claim_map:
            _issue(
                issues,
                "error",
                "claim-id-duplicate",
                f"事实编号重复：{claim_id}",
                f"{path}.id",
            )
        else:
            claim_map[claim_id] = claim
        if not statement:
            _issue(
                issues,
                "error",
                "claim-statement-missing",
                "事实主张缺少可直接核验的 statement",
                f"{path}.statement",
            )
        if not segment_ids:
            _issue(
                issues,
                "error",
                "claim-segments-missing",
                "事实主张至少关联一个段落",
                f"{path}.segment_ids",
            )
        for segment_id in segment_ids:
            if segment_id not in segment_map:
                _issue(
                    issues,
                    "error",
                    "claim-segment-unknown",
                    f"事实主张引用了未声明段号：{segment_id}",
                    f"{path}.segment_ids",
                )
            elif claim_id not in segment_claim_ids.get(segment_id, []):
                _issue(
                    issues,
                    "error",
                    "claim-segment-link-mismatch",
                    f"段 {segment_id} 的 claim_ids 未包含 {claim_id}",
                    f"{path}.segment_ids",
                )
        if not evidence_ids:
            _issue(
                issues,
                "error",
                "claim-evidence-missing",
                "事实主张至少关联一条证据",
                f"{path}.evidence_ids",
            )
        if risk_level not in RISK_LEVELS:
            _issue(
                issues,
                "error",
                "claim-risk-invalid",
                "risk_level 必须是 low、medium 或 high",
                f"{path}.risk_level",
            )
        if category not in CLAIM_CATEGORIES:
            _issue(
                issues,
                "error",
                "claim-category-invalid",
                "claim category 不在允许范围内",
                f"{path}.category",
            )
        if verification_status not in VERIFICATION_STATUSES:
            _issue(
                issues,
                "error",
                "claim-status-invalid",
                "verification_status 不在允许范围内",
                f"{path}.verification_status",
            )
        elif verification_status != "verified":
            _issue(
                issues,
                "error",
                "claim-not-verified",
                f"事实 {claim_id or index + 1} 尚未核验，不能进入正式交付",
                f"{path}.verification_status",
            )
        for evidence_id in evidence_ids:
            evidence_usage.setdefault(evidence_id, []).append(claim_id)

    for segment_id, claim_ids in segment_claim_ids.items():
        for claim_id in claim_ids:
            if claim_id not in claim_map:
                _issue(
                    issues,
                    "error",
                    "segment-claim-unknown",
                    f"段 {segment_id} 引用了未声明事实：{claim_id}",
                    "$.segments",
                )
            elif segment_id not in _unique_texts(claim_map[claim_id].get("segment_ids")):
                _issue(
                    issues,
                    "error",
                    "segment-claim-link-mismatch",
                    f"事实 {claim_id} 的 segment_ids 未包含段 {segment_id}",
                    "$.segments",
                )

    evidence = _items(script.get("evidence"))
    evidence_map: dict[str, dict[str, object]] = {}
    for index, entry in enumerate(evidence):
        item = _mapping(entry)
        evidence_id = _text(item.get("id"))
        source_type = _text(item.get("source_type"))
        source_title = _text(item.get("source_title"))
        publisher = _text(item.get("publisher"))
        url_or_identifier = _text(item.get("url_or_identifier"))
        published_date = _text(item.get("published_date"))
        accessed_date = _text(item.get("accessed_date"))
        reliability = _text(item.get("reliability"))
        status = _text(item.get("status"))
        supports = _text(item.get("supports"))
        path = f"$.evidence[{index}]"

        if not evidence_id or not EVIDENCE_ID_RE.fullmatch(evidence_id):
            _issue(
                issues,
                "error",
                "evidence-id-invalid",
                "证据编号必须使用 E1、E2 一类格式",
                f"{path}.id",
            )
        elif evidence_id in evidence_map:
            _issue(
                issues,
                "error",
                "evidence-id-duplicate",
                f"证据编号重复：{evidence_id}",
                f"{path}.id",
            )
        else:
            evidence_map[evidence_id] = item
        if source_type not in SOURCE_TYPES:
            _issue(
                issues,
                "error",
                "evidence-source-type-invalid",
                "source_type 不在允许范围内",
                f"{path}.source_type",
            )
        if not source_title:
            _issue(
                issues,
                "error",
                "evidence-source-title-missing",
                "证据缺少来源标题",
                f"{path}.source_title",
            )
        if not publisher:
            _issue(
                issues,
                "error",
                "evidence-publisher-missing",
                "证据缺少发布机构",
                f"{path}.publisher",
            )
        if not url_or_identifier and source_type != "user_material":
            _issue(
                issues,
                "error",
                "evidence-locator-missing",
                "非用户资料证据必须提供 url_or_identifier",
                f"{path}.url_or_identifier",
            )
        if published_date and not _valid_iso_date(published_date):
            _issue(
                issues,
                "error",
                "evidence-published-date-invalid",
                "published_date 必须使用 YYYY-MM-DD",
                f"{path}.published_date",
            )
        if not accessed_date or not _valid_iso_date(accessed_date):
            _issue(
                issues,
                "error",
                "evidence-accessed-date-invalid",
                "accessed_date 必须使用 YYYY-MM-DD",
                f"{path}.accessed_date",
            )
        if reliability not in RELIABILITY_LEVELS:
            _issue(
                issues,
                "error",
                "evidence-reliability-invalid",
                "reliability 必须是 high、medium 或 low",
                f"{path}.reliability",
            )
        if status not in EVIDENCE_STATUSES:
            _issue(
                issues,
                "error",
                "evidence-status-invalid",
                "status 不在允许范围内",
                f"{path}.status",
            )
        if not supports:
            _issue(
                issues,
                "error",
                "evidence-support-missing",
                "证据缺少 supports，无法确认具体支持了哪一部分主张",
                f"{path}.supports",
            )
        if evidence_id and evidence_id not in evidence_usage:
            _issue(
                issues,
                "warning",
                "evidence-unused",
                f"证据 {evidence_id} 未被任何事实主张引用",
                f"{path}.id",
            )

    for claim_id, claim in claim_map.items():
        evidence_ids = _unique_texts(claim.get("evidence_ids"))
        linked_evidence = [
            evidence_map[evidence_id]
            for evidence_id in evidence_ids
            if evidence_id in evidence_map
        ]
        for evidence_id in evidence_ids:
            if evidence_id not in evidence_map:
                _issue(
                    issues,
                    "error",
                    "claim-evidence-unknown",
                    f"事实 {claim_id} 引用了未声明证据：{evidence_id}",
                    "$.claims",
                )
        if not linked_evidence:
            continue
        if any(_text(item.get("status")) != "verified" for item in linked_evidence):
            _issue(
                issues,
                "error",
                "claim-evidence-not-verified",
                f"事实 {claim_id} 仍引用未核验、部分核验或争议证据",
                "$.claims",
            )
        if any(_text(item.get("reliability")) == "low" for item in linked_evidence):
            _issue(
                issues,
                "error",
                "claim-evidence-low-reliability",
                f"事实 {claim_id} 不能只靠低可靠度证据进入正式交付",
                "$.claims",
            )
        risk_level = _text(claim.get("risk_level"))
        high_count = sum(
            1
            for item in linked_evidence
            if _text(item.get("reliability")) == "high"
        )
        medium_count = sum(
            1
            for item in linked_evidence
            if _text(item.get("reliability")) == "medium"
        )
        if risk_level == "high" and (
            len(linked_evidence) < 2 or high_count < 1
        ):
            _issue(
                issues,
                "error",
                "claim-high-risk-evidence-insufficient",
                f"高风险事实 {claim_id} 至少需要两条证据，其中至少一条为高可靠度",
                "$.claims",
            )
        if risk_level == "medium" and high_count == 0 and medium_count < 2:
            _issue(
                issues,
                "error",
                "claim-medium-risk-evidence-insufficient",
                f"中风险事实 {claim_id} 无高可靠度来源时，至少需要两条中可靠度来源",
                "$.claims",
            )
        category = _text(claim.get("category"))
        if category in {"medical", "legal"}:
            if risk_level != "high":
                _issue(
                    issues,
                    "error",
                    "medical-legal-risk-level",
                    f"医疗或法律事实 {claim_id} 必须标记为 high 风险",
                    "$.claims",
                )
            authoritative_count = sum(
                1
                for item in linked_evidence
                if _text(item.get("source_type")) in AUTHORITATIVE_SOURCE_TYPES
                and _text(item.get("reliability")) == "high"
            )
            if len(linked_evidence) < 2 or authoritative_count < 2:
                _issue(
                    issues,
                    "error",
                    "medical-legal-evidence-insufficient",
                    f"医疗或法律事实 {claim_id} 至少需要两条高可靠度的官方、学术、原始或专业来源",
                    "$.claims",
                )

    full_text = narration_text(script)
    for marker in tone_markers:
        if marker not in full_text:
            _issue(
                issues,
                "error",
                "tone-marker-missing-from-copy",
                f"表达标记未进入正文：{marker}",
                "$.segments",
            )
    if project_domain == "geography_travel":
        for role_name in role_names:
            if role_name not in full_text:
                _issue(
                    issues,
                    "error",
                    "content-role-missing-from-copy",
                    f"地理文旅项目中的地点或对象未进入正文：{role_name}",
                    "$.segments",
                )

    for phrase in HYPE_PHRASES:
        if phrase in full_text:
            _issue(
                issues,
                "warning",
                "hype-expression",
                f"发现空泛夸张表达：{phrase}",
                "$.segments",
            )
    for phrase in FILLER_PHRASES:
        if phrase in full_text:
            _issue(
                issues,
                "warning",
                "filler-expression",
                f"发现模板套话：{phrase}",
                "$.segments",
            )
    forbidden_advice = FORBIDDEN_ADVICE_RE.search(full_text)
    if forbidden_advice:
        _issue(
            issues,
            "error",
            "forbidden-medical-legal-advice",
            f"正文含个体医疗或法律建议禁则：{forbidden_advice.group(0)}",
            "$.segments",
        )

    titles = _unique_texts(script.get("titles"))
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
    delivery_date = _text(delivery.get("date"))
    if not version:
        _issue(
            issues,
            "error",
            "version-missing",
            "缺少交付版本",
            "$.delivery.version",
        )
    if not delivery_date or not _valid_iso_date(delivery_date):
        _issue(
            issues,
            "error",
            "delivery-date-invalid",
            "交付日期必须使用 YYYY-MM-DD",
            "$.delivery.date",
        )

    char_count = effective_char_count(full_text)
    estimated_min = estimate_seconds(char_count, FAST_CPM)
    estimated_max = estimate_seconds(char_count, SLOW_CPM)
    recommended_target = estimate_seconds(char_count, DEFAULT_CPM)
    duration_tolerance = max(5.0, duration * 0.10)
    target_min = max(0.0, duration - duration_tolerance)
    target_max = duration + duration_tolerance
    if duration > 0 and not _ranges_overlap(
        estimated_min,
        estimated_max,
        target_min,
        target_max,
    ):
        _issue(
            issues,
            "error",
            "overall-reading-duration-mismatch",
            (
                f"全文有效字符 {char_count}，估算 {estimated_min:.1f} 至 "
                f"{estimated_max:.1f} 秒，与目标区间 {target_min:.1f} 至 "
                f"{target_max:.1f} 秒不重叠"
            ),
            "$.segments",
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
            "domain": project_domain,
            "project_type": project_type,
            "topic": topic,
            "audience": audience,
            "tone": tone,
            "platform": platform,
            "duration_seconds": round(duration, 2),
            "series": series_info,
        },
        "metrics": {
            "effective_char_count": char_count,
            "timeline_start_seconds": 0.0,
            "timeline_end_seconds": round(final_end, 2),
            "segment_count": len(segment_reports),
            "claim_count": len(claim_map),
            "evidence_count": len(evidence_map),
            "verified_claim_count": sum(
                1
                for item in claim_map.values()
                if _text(item.get("verification_status")) == "verified"
            ),
            "estimated_seconds": {
                "minimum_at_210_cpm": round(estimated_min, 2),
                "maximum_at_170_cpm": round(estimated_max, 2),
                "target_at_190_cpm": round(recommended_target, 2),
            },
            "segments": segment_reports,
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
                if (
                    part in names
                    and (part.endswith(".xml") or part.endswith(".rels"))
                ):
                    try:
                        ElementTree.fromstring(archive.read(part))
                    except ElementTree.ParseError as exc:
                        errors.append(f"{part} XML 无法解析：{exc}")
    except (OSError, zipfile.BadZipFile) as exc:
        errors.append(f"无法读取 DOCX：{exc}")

    return errors
