#!/usr/bin/env python3
"""Build and check the three-part narration delivery package."""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree
from xml.sax.saxutils import escape

from script_contract import (
    DOCX_REQUIRED_PARTS,
    check_docx,
    format_time_range,
    load_json,
    validate_script,
)


W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
READABLE_NAME = "01_可朗读正文.docx"
REVIEW_NAME = "02_项目审阅.docx"
EVIDENCE_NAME = "03_证据表.csv"
PACKAGE_FILES = (READABLE_NAME, REVIEW_NAME, EVIDENCE_NAME)

DOMAIN_LABELS = {
    "history_culture": "历史文化",
    "geography_travel": "地理文旅",
    "life_skill": "生活技能",
}
PROJECT_TYPE_LABELS = {"single": "单集", "series": "系列"}
RISK_LABELS = {"low": "低", "medium": "中", "high": "高"}
CATEGORY_LABELS = {
    "historical": "历史",
    "cultural": "文化",
    "geographic": "地理",
    "scientific": "科学",
    "life_practice": "生活实践",
    "safety": "安全",
    "medical": "医疗",
    "legal": "法律",
    "other": "其他",
}
STATUS_LABELS = {
    "verified": "已核验",
    "partial": "部分核验",
    "unverified": "未核验",
    "disputed": "有争议",
}
SOURCE_TYPE_LABELS = {
    "official": "官方机构",
    "academic": "学术机构",
    "primary": "原始文献",
    "professional": "专业机构",
    "authoritative_media": "权威媒体",
    "user_material": "用户资料",
}
RELIABILITY_LABELS = {"high": "高", "medium": "中", "low": "低"}


def _mapping(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}


def _items(value: object) -> list[object]:
    return value if isinstance(value, list) else []


def _text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _paragraph(
    text: str,
    style: str | None = None,
    *,
    bold: bool = False,
    size: int | None = None,
    align: str | None = None,
    keep_next: bool = False,
    before: int = 0,
    after: int = 0,
    line: int = 340,
    color: str | None = None,
) -> str:
    properties: list[str] = []
    if style:
        properties.append(f'<w:pStyle w:val="{style}"/>')
    if keep_next:
        properties.append("<w:keepNext/>")
    if align:
        properties.append(f'<w:jc w:val="{align}"/>')
    properties.append(
        f'<w:spacing w:before="{before}" w:after="{after}" '
        f'w:line="{line}" w:lineRule="auto"/>'
    )
    return (
        "<w:p>"
        f"<w:pPr>{''.join(properties)}</w:pPr>"
        f"{_run(text, bold=bold, size=size, color=color)}"
        "</w:p>"
    )


def _run(
    text: str,
    *,
    bold: bool = False,
    size: int | None = None,
    color: str | None = None,
) -> str:
    run_properties = [
        '<w:rFonts w:ascii="Aptos" w:hAnsi="Aptos" w:eastAsia="微软雅黑"/>'
    ]
    if bold:
        run_properties.append("<w:b/>")
    if color:
        run_properties.append(f'<w:color w:val="{color}"/>')
    if size:
        run_properties.append(f'<w:sz w:val="{size}"/><w:szCs w:val="{size}"/>')
    content: list[str] = []
    for index, line in enumerate(text.split("\n")):
        if index:
            content.append("<w:br/>")
        content.append(f'<w:t xml:space="preserve">{escape(line)}</w:t>')
    return f"<w:r><w:rPr>{''.join(run_properties)}</w:rPr>{''.join(content)}</w:r>"


def _cell(
    text: str,
    width: int,
    *,
    header: bool = False,
    align: str = "left",
    size: int = 20,
) -> str:
    shading = '<w:shd w:val="clear" w:fill="F2F2F2"/>' if header else ""
    return (
        "<w:tc>"
        "<w:tcPr>"
        f'<w:tcW w:w="{width}" w:type="dxa"/>'
        f"{shading}"
        '<w:vAlign w:val="center"/>'
        "</w:tcPr>"
        f"{_paragraph(text, 'TableText', bold=header, size=size, align=align, line=260)}"
        "</w:tc>"
    )


def _table(
    headers: list[str],
    rows: list[list[str]],
    widths: list[int],
    *,
    table_width: int = 9600,
    size: int = 20,
) -> str:
    border = (
        "<w:tblBorders>"
        '<w:top w:val="single" w:sz="4" w:color="D9D9D9"/>'
        '<w:left w:val="single" w:sz="4" w:color="D9D9D9"/>'
        '<w:bottom w:val="single" w:sz="4" w:color="D9D9D9"/>'
        '<w:right w:val="single" w:sz="4" w:color="D9D9D9"/>'
        '<w:insideH w:val="single" w:sz="4" w:color="D9D9D9"/>'
        '<w:insideV w:val="single" w:sz="4" w:color="D9D9D9"/>'
        "</w:tblBorders>"
    )
    grid = "".join(f'<w:gridCol w:w="{width}"/>' for width in widths)
    header_row = (
        "<w:tr><w:trPr><w:tblHeader/></w:trPr>"
        + "".join(
            _cell(text, widths[index], header=True, size=size)
            for index, text in enumerate(headers)
        )
        + "</w:tr>"
    )
    body_rows = [
        "<w:tr>"
        + "".join(
            _cell(text, widths[index], size=size)
            for index, text in enumerate(row)
        )
        + "</w:tr>"
        for row in rows
    ]
    return (
        "<w:tbl>"
        "<w:tblPr>"
        f'<w:tblW w:w="{table_width}" w:type="dxa"/>'
        '<w:tblLayout w:type="fixed"/>'
        f"{border}"
        "</w:tblPr>"
        f"<w:tblGrid>{grid}</w:tblGrid>"
        f"{header_row}{''.join(body_rows)}"
        "</w:tbl>"
    )


def _content_types() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
  <Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
  <Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
  <Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
</Types>
"""


def _root_rels() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>
"""


def _document_rels() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>
"""


def _styles_xml(*, readable: bool) -> str:
    body_size = 28 if readable else 22
    body_line = 380 if readable else 340
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="{W_NS}">
  <w:docDefaults>
    <w:rPrDefault>
      <w:rPr>
        <w:rFonts w:ascii="Aptos" w:hAnsi="Aptos" w:eastAsia="微软雅黑"/>
        <w:sz w:val="{body_size}"/>
        <w:szCs w:val="{body_size}"/>
      </w:rPr>
    </w:rPrDefault>
    <w:pPrDefault>
      <w:pPr>
        <w:spacing w:after="140" w:line="{body_line}" w:lineRule="auto"/>
      </w:pPr>
    </w:pPrDefault>
  </w:docDefaults>
  <w:style w:type="paragraph" w:default="1" w:styleId="Normal">
    <w:name w:val="Normal"/>
    <w:qFormat/>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Title">
    <w:name w:val="Title"/>
    <w:basedOn w:val="Normal"/>
    <w:next w:val="Normal"/>
    <w:qFormat/>
    <w:rPr>
      <w:b/>
      <w:sz w:val="36"/>
      <w:szCs w:val="36"/>
    </w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Subtitle">
    <w:name w:val="Subtitle"/>
    <w:basedOn w:val="Normal"/>
    <w:next w:val="Normal"/>
    <w:rPr>
      <w:color w:val="666666"/>
      <w:sz w:val="20"/>
      <w:szCs w:val="20"/>
    </w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Heading1">
    <w:name w:val="heading 1"/>
    <w:basedOn w:val="Normal"/>
    <w:next w:val="Normal"/>
    <w:qFormat/>
    <w:pPr>
      <w:keepNext/>
      <w:spacing w:before="300" w:after="120" w:line="300" w:lineRule="auto"/>
      <w:outlineLvl w:val="0"/>
    </w:pPr>
    <w:rPr>
      <w:b/>
      <w:sz w:val="30"/>
      <w:szCs w:val="30"/>
    </w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Heading2">
    <w:name w:val="heading 2"/>
    <w:basedOn w:val="Normal"/>
    <w:next w:val="Normal"/>
    <w:qFormat/>
    <w:pPr>
      <w:keepNext/>
      <w:spacing w:before="240" w:after="80" w:line="300" w:lineRule="auto"/>
      <w:outlineLvl w:val="1"/>
    </w:pPr>
    <w:rPr>
      <w:b/>
      <w:sz w:val="26"/>
      <w:szCs w:val="26"/>
    </w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="BodyText">
    <w:name w:val="Body Text"/>
    <w:basedOn w:val="Normal"/>
    <w:pPr>
      <w:spacing w:after="160" w:line="{body_line}" w:lineRule="auto"/>
    </w:pPr>
    <w:rPr>
      <w:sz w:val="{body_size}"/>
      <w:szCs w:val="{body_size}"/>
    </w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Note">
    <w:name w:val="Note"/>
    <w:basedOn w:val="Normal"/>
    <w:rPr>
      <w:color w:val="666666"/>
      <w:sz w:val="20"/>
      <w:szCs w:val="20"/>
    </w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="TableText">
    <w:name w:val="Table Text"/>
    <w:basedOn w:val="Normal"/>
    <w:pPr>
      <w:spacing w:before="50" w:after="50" w:line="270" w:lineRule="auto"/>
    </w:pPr>
    <w:rPr>
      <w:sz w:val="20"/>
      <w:szCs w:val="20"/>
    </w:rPr>
  </w:style>
</w:styles>
"""


def _core_properties(title: str, delivery_date: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <dc:title>{escape(title)}</dc:title>
  <dc:creator>Codex</dc:creator>
  <cp:lastModifiedBy>Codex</cp:lastModifiedBy>
  <dcterms:created xsi:type="dcterms:W3CDTF">{escape(delivery_date)}T00:00:00Z</dcterms:created>
  <dcterms:modified xsi:type="dcterms:W3CDTF">{escape(delivery_date)}T00:00:00Z</dcterms:modified>
</cp:coreProperties>
"""


def _app_properties() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">
  <Application>Codex</Application>
  <DocSecurity>0</DocSecurity>
  <ScaleCrop>false</ScaleCrop>
  <Company></Company>
  <AppVersion>1.0</AppVersion>
</Properties>
"""


def _document_wrapper(parts: list[str], *, readable: bool) -> str:
    top = "1080" if readable else "1000"
    bottom = "1080" if readable else "1000"
    left = "1080" if readable else "1000"
    right = "1080" if readable else "1000"
    section_properties = (
        "<w:sectPr>"
        '<w:pgSz w:w="11906" w:h="16838"/>'
        f'<w:pgMar w:top="{top}" w:right="{right}" w:bottom="{bottom}" '
        f'w:left="{left}" w:header="720" w:footer="720" w:gutter="0"/>'
        "</w:sectPr>"
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<w:document xmlns:w="{W_NS}">'
        f"<w:body>{''.join(parts)}{section_properties}</w:body>"
        "</w:document>"
    )


def _write_docx(
    output: Path,
    document_xml: str,
    *,
    readable: bool,
    title: str,
    delivery_date: str,
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", _content_types())
        archive.writestr("_rels/.rels", _root_rels())
        archive.writestr("word/document.xml", document_xml)
        archive.writestr("word/_rels/document.xml.rels", _document_rels())
        archive.writestr("word/styles.xml", _styles_xml(readable=readable))
        archive.writestr(
            "docProps/core.xml",
            _core_properties(title=title, delivery_date=delivery_date),
        )
        archive.writestr("docProps/app.xml", _app_properties())
    errors = check_docx(output)
    if errors:
        raise ValueError("; ".join(errors))


def _segment_rows(script: dict[str, object]) -> list[list[str]]:
    rows: list[list[str]] = []
    for segment in _items(script.get("segments")):
        item = _mapping(segment)
        rows.append(
            [
                (
                    f"{_text(item.get('id'))}："
                    + format_time_range(
                        float(item["start_seconds"]),
                        float(item["end_seconds"]),
                    )
                ),
                _text(item.get("title")),
                "、".join(
                    _text(value) for value in _items(item.get("claim_ids"))
                )
                or "无",
            ]
        )
    return rows


def _readable_document_xml(script: dict[str, object]) -> str:
    project = _mapping(script.get("project"))
    delivery = _mapping(script.get("delivery"))
    project_name = _text(project.get("name"))
    duration = float(project["duration_seconds"])
    version = _text(delivery.get("version"))
    delivery_date = _text(delivery.get("date"))
    parts = [
        _paragraph(
            f"{project_name}｜可朗读正文",
            "Title",
            align="center",
            after=100,
        ),
        _paragraph(
            f"中老年受众版 | {version} | {delivery_date}",
            "Subtitle",
            align="center",
            after=260,
        ),
        _paragraph("视频文案顺序与占用时间表", "Heading1"),
        _table(
            ["文案顺序与占用时间", "段落主题", "关联事实"],
            _segment_rows(script),
            [2300, 4300, 3000],
            size=22,
        ),
        _paragraph(
            f"全片时间：00:00-{format_time_range(0, duration).split('-', 1)[1]}",
            "Note",
            before=100,
            after=260,
        ),
        _paragraph("可朗读正文", "Heading1"),
    ]

    for segment in _items(script.get("segments")):
        item = _mapping(segment)
        segment_id = _text(item.get("id"))
        title = _text(item.get("title"))
        time_range = format_time_range(
            float(item["start_seconds"]),
            float(item["end_seconds"]),
        )
        parts.append(
            _paragraph(
                f"{segment_id}：{time_range}｜{title}",
                "Heading2",
            )
        )
        paragraphs = [
            paragraph.strip()
            for paragraph in _text(item.get("text")).split("\n")
            if paragraph.strip()
        ]
        parts.extend(_paragraph(value, "BodyText") for value in paragraphs)
        reading_notes = _text(item.get("reading_notes"))
        if reading_notes:
            parts.append(
                _paragraph(f"朗读提示：{reading_notes}", "Note", after=180)
            )

    parts.extend(
        [
            _paragraph("文件说明", "Heading1"),
            _paragraph(
                "本文件用于配音和逐段审听。事实核验、来源和质量状态见项目审阅文档与证据表。",
                "Note",
            ),
        ]
    )
    return _document_wrapper(parts, readable=True)


def _claim_time_ranges(
    claim: dict[str, object],
    segment_map: dict[str, dict[str, object]],
) -> str:
    ranges: list[str] = []
    for segment_id in _items(claim.get("segment_ids")):
        segment = segment_map.get(_text(segment_id))
        if not segment:
            continue
        ranges.append(
            format_time_range(
                float(segment["start_seconds"]),
                float(segment["end_seconds"]),
            )
        )
    return "、".join(ranges)


def _review_document_xml(
    script: dict[str, object],
    report: dict[str, object],
) -> str:
    project = _mapping(script.get("project"))
    strategy = _mapping(script.get("strategy"))
    delivery = _mapping(script.get("delivery"))
    metrics = _mapping(report.get("metrics"))
    project_name = _text(project.get("name"))
    domain = _text(project.get("domain"))
    project_type = _text(project.get("project_type"))
    duration = float(project["duration_seconds"])
    version = _text(delivery.get("version"))
    delivery_date = _text(delivery.get("date"))

    segments = [_mapping(item) for item in _items(script.get("segments"))]
    segment_map = {_text(item.get("id")): item for item in segments}
    parts = [
        _paragraph(f"{project_name}｜项目审阅文档", "Title", align="center", after=100),
        _paragraph(
            f"{version} | {delivery_date}",
            "Subtitle",
            align="center",
            after=260,
        ),
        _paragraph("视频文案顺序与占用时间表", "Heading1"),
        _table(
            ["文案顺序与占用时间", "段落主题", "关联事实"],
            _segment_rows(script),
            [2300, 4300, 3000],
            size=20,
        ),
        _paragraph("项目概览", "Heading1"),
        _table(
            ["项目", "内容"],
            [
                ["项目名称", project_name],
                ["内容领域", DOMAIN_LABELS.get(domain, domain)],
                ["项目类型", PROJECT_TYPE_LABELS.get(project_type, project_type)],
                ["核心主题", _text(project.get("topic"))],
                ["目标受众", _text(project.get("audience"))],
                ["视频时长", f"{duration:g} 秒"],
                ["发布平台", _text(project.get("platform")) or "未指定"],
                ["语气基调", _text(project.get("tone")) or "平实清楚"],
            ],
            [2200, 7400],
        ),
    ]

    series = _mapping(project.get("series"))
    if project_type == "series":
        parts.extend(
            [
                _paragraph("系列位置", "Heading1"),
                _table(
                    ["项目", "内容"],
                    [
                        ["系列名称", _text(series.get("series_title"))],
                        [
                            "本集位置",
                            (
                                f"第 {int(series['episode_number'])} 集 / "
                                f"共 {int(series['total_episodes'])} 集"
                            ),
                        ],
                        ["本集名称", _text(series.get("episode_title"))],
                        ["承上启下职责", _text(series.get("arc_role"))],
                    ],
                    [2200, 7400],
                ),
            ]
        )

    parts.extend(
        [
            _paragraph("创作策略与中老年适配", "Heading1"),
            _paragraph(f"核心主题：{_text(strategy.get('core_theme'))}", "BodyText"),
            _paragraph(f"进入设计：{_text(strategy.get('opening_angle'))}", "BodyText"),
            _paragraph(f"收束设计：{_text(strategy.get('closing_idea'))}", "BodyText"),
            _paragraph("内容职责", "Heading2"),
            _table(
                ["内容对象", "叙事职责"],
                [
                    [
                        _text(_mapping(item).get("name")),
                        _text(_mapping(item).get("role")),
                    ]
                    for item in _items(strategy.get("content_roles"))
                ],
                [2400, 7200],
            ),
            _paragraph("受众适配", "Heading2"),
        ]
    )
    for adaptation in _items(strategy.get("audience_adaptations")):
        parts.append(_paragraph(f"- {_text(adaptation)}", "BodyText"))
    parts.append(
        _paragraph(
            "表达标记：" + "、".join(_text(value) for value in _items(strategy.get("tone_markers"))),
            "BodyText",
        )
    )

    claim_rows: list[list[str]] = []
    evidence_rows: list[list[str]] = []
    evidence_map: dict[str, dict[str, object]] = {}
    for evidence in _items(script.get("evidence")):
        item = _mapping(evidence)
        evidence_map[_text(item.get("id"))] = item

    for claim in _items(script.get("claims")):
        item = _mapping(claim)
        evidence_ids = [
            _text(value) for value in _items(item.get("evidence_ids"))
        ]
        source_names = [
            _text(evidence_map.get(evidence_id, {}).get("source_title"))
            for evidence_id in evidence_ids
        ]
        claim_rows.append(
            [
                _text(item.get("id")),
                _text(item.get("statement")),
                RISK_LABELS.get(_text(item.get("risk_level")), _text(item.get("risk_level"))),
                CATEGORY_LABELS.get(_text(item.get("category")), _text(item.get("category"))),
                STATUS_LABELS.get(
                    _text(item.get("verification_status")),
                    _text(item.get("verification_status")),
                ),
                _claim_time_ranges(item, segment_map),
                "、".join(item_id for item_id in evidence_ids if item_id),
                "；".join(name for name in source_names if name),
            ]
        )

    for evidence in _items(script.get("evidence")):
        item = _mapping(evidence)
        evidence_rows.append(
            [
                _text(item.get("id")),
                _text(item.get("source_title")),
                _text(item.get("publisher")),
                SOURCE_TYPE_LABELS.get(
                    _text(item.get("source_type")),
                    _text(item.get("source_type")),
                ),
                RELIABILITY_LABELS.get(
                    _text(item.get("reliability")),
                    _text(item.get("reliability")),
                ),
                STATUS_LABELS.get(
                    _text(item.get("status")),
                    _text(item.get("status")),
                ),
                _text(item.get("supports")),
            ]
        )

    parts.extend(
        [
            _paragraph("事实核验总览", "Heading1"),
            _table(
                [
                    "事实",
                    "主张",
                    "风险",
                    "类型",
                    "状态",
                    "时间位置",
                    "证据",
                    "来源",
                ],
                claim_rows,
                [700, 2200, 650, 800, 900, 1500, 900, 1950],
                size=18,
            ),
            _paragraph("证据清单摘要", "Heading1"),
            _table(
                ["证据", "来源标题", "发布机构", "类型", "可靠度", "状态", "支持内容"],
                evidence_rows,
                [700, 2100, 1500, 1000, 750, 850, 2700],
                size=18,
            ),
        ]
    )

    estimated = _mapping(metrics.get("estimated_seconds"))
    parts.extend(
        [
            _paragraph("朗读与时间审阅", "Heading1"),
            _table(
                ["指标", "结果"],
                [
                    [
                        "时间轴",
                        (
                            "00:00-"
                            + format_time_range(
                                0,
                                float(metrics.get("timeline_end_seconds", duration)),
                            ).split("-", 1)[1]
                        ),
                    ],
                    ["段落数", str(metrics.get("segment_count", 0))],
                    ["有效字符", str(metrics.get("effective_char_count", 0))],
                    [
                        "预计朗读",
                        (
                            format_time_range(
                                float(estimated.get("minimum_at_210_cpm", 0)),
                                float(estimated.get("maximum_at_170_cpm", 0)),
                            )
                            + "（按每分钟 210 至 170 个有效字符估算）"
                        ),
                    ],
                    ["事实数量", str(metrics.get("claim_count", 0))],
                    ["证据数量", str(metrics.get("evidence_count", 0))],
                    [
                        "已核验事实",
                        str(metrics.get("verified_claim_count", 0)),
                    ],
                ],
                [2400, 7200],
            ),
        ]
    )

    warnings = [
        _mapping(item)
        for item in _items(report.get("issues"))
        if _mapping(item).get("level") == "warning"
    ]
    parts.extend(
        [
            _paragraph("发布前复核", "Heading1"),
            _table(
                ["检查项", "状态"],
                [
                    ["时间轴连续且与总时长一致", "通过"],
                    ["每条正式事实均已核验", "通过" if not any(
                        _mapping(item).get("code") in {
                            "claim-not-verified",
                            "claim-evidence-not-verified",
                        }
                        for item in _items(report.get("issues"))
                    ) else "未通过"],
                    ["高风险事实证据数量与可靠度", "通过" if not any(
                        "high-risk" in _text(_mapping(item).get("code"))
                        for item in _items(report.get("issues"))
                    ) else "未通过"],
                    ["中老年朗读节奏", "通过" if not any(
                        _text(_mapping(item).get("code")) in {
                            "segment-reading-duration-mismatch",
                            "sentence-too-long",
                            "overall-reading-duration-mismatch",
                        }
                        for item in _items(report.get("issues"))
                    ) else "未通过"],
                    ["医疗法律个体建议禁则", "通过" if not any(
                        _text(_mapping(item).get("code"))
                        == "forbidden-medical-legal-advice"
                        for item in _items(report.get("issues"))
                    ) else "未通过"],
                    [
                        "未关闭 warning",
                        "无"
                        if not warnings
                        else "\n".join(
                            f"- {_text(item.get('message'))}"
                            for item in warnings
                        ),
                    ],
                ],
                [3000, 6600],
            ),
        ]
    )

    delivery_notes = _text(delivery.get("notes"))
    if delivery_notes:
        parts.extend(
            [
                _paragraph("交付备注", "Heading1"),
                _paragraph(delivery_notes, "BodyText"),
            ]
        )

    return _document_wrapper(parts, readable=False)


def _csv_cell(value: object) -> str:
    text = str(value)
    if text.startswith(("=", "+", "-", "@")):
        return "'" + text
    return text


def _evidence_csv(script: dict[str, object]) -> bytes:
    claims = [_mapping(item) for item in _items(script.get("claims"))]
    evidence = {
        _text(_mapping(item).get("id")): _mapping(item)
        for item in _items(script.get("evidence"))
    }
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(
        [
            "证据编号",
            "事实编号",
            "事实陈述",
            "关联段落",
            "风险等级",
            "事实类型",
            "事实核验状态",
            "来源类型",
            "来源标题",
            "发布机构",
            "作者",
            "来源网址或标识",
            "发布日期",
            "访问日期",
            "可靠度",
            "证据状态",
            "支持内容",
            "核验备注",
        ]
    )
    for claim in claims:
        claim_id = _text(claim.get("id"))
        for evidence_id in _items(claim.get("evidence_ids")):
            evidence_key = _text(evidence_id)
            item = evidence.get(evidence_key, {})
            writer.writerow(
                [
                    _csv_cell(evidence_key),
                    _csv_cell(claim_id),
                    _csv_cell(_text(claim.get("statement"))),
                    _csv_cell(
                        "、".join(
                            _text(value)
                            for value in _items(claim.get("segment_ids"))
                        )
                    ),
                    _csv_cell(
                        RISK_LABELS.get(
                            _text(claim.get("risk_level")),
                            _text(claim.get("risk_level")),
                        )
                    ),
                    _csv_cell(
                        CATEGORY_LABELS.get(
                            _text(claim.get("category")),
                            _text(claim.get("category")),
                        )
                    ),
                    _csv_cell(
                        STATUS_LABELS.get(
                            _text(claim.get("verification_status")),
                            _text(claim.get("verification_status")),
                        )
                    ),
                    _csv_cell(
                        SOURCE_TYPE_LABELS.get(
                            _text(item.get("source_type")),
                            _text(item.get("source_type")),
                        )
                    ),
                    _csv_cell(_text(item.get("source_title"))),
                    _csv_cell(_text(item.get("publisher"))),
                    _csv_cell(_text(item.get("author"))),
                    _csv_cell(_text(item.get("url_or_identifier"))),
                    _csv_cell(_text(item.get("published_date"))),
                    _csv_cell(_text(item.get("accessed_date"))),
                    _csv_cell(
                        RELIABILITY_LABELS.get(
                            _text(item.get("reliability")),
                            _text(item.get("reliability")),
                        )
                    ),
                    _csv_cell(
                        STATUS_LABELS.get(
                            _text(item.get("status")),
                            _text(item.get("status")),
                        )
                    ),
                    _csv_cell(_text(item.get("supports"))),
                    _csv_cell(_text(item.get("notes"))),
                ]
            )
    return b"\xef\xbb\xbf" + output.getvalue().encode("utf-8")


def _slug(value: str) -> str:
    text = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", value).strip(" ._")
    return text or "视频旁白交付包"


def build_package(
    script: dict[str, object],
    output_dir: Path,
    *,
    output_zip: Path | None = None,
) -> dict[str, object]:
    report = validate_script(script)
    if report["error_count"]:
        details = "; ".join(
            _text(item.get("message"))
            for item in _items(report.get("issues"))
            if _text(item.get("level")) == "error"
        )
        raise ValueError(f"script contract failed: {details}")

    project = _mapping(script.get("project"))
    delivery = _mapping(script.get("delivery"))
    project_name = _text(project.get("name"))
    output_dir.mkdir(parents=True, exist_ok=True)
    readable_path = output_dir / READABLE_NAME
    review_path = output_dir / REVIEW_NAME
    evidence_path = output_dir / EVIDENCE_NAME

    _write_docx(
        readable_path,
        _readable_document_xml(script),
        readable=True,
        title=f"{project_name} 可朗读正文",
        delivery_date=_text(delivery.get("date")),
    )
    _write_docx(
        review_path,
        _review_document_xml(script, report),
        readable=False,
        title=f"{project_name} 项目审阅文档",
        delivery_date=_text(delivery.get("date")),
    )
    evidence_path.write_bytes(_evidence_csv(script))

    package_path = output_zip or output_dir.parent / f"{_slug(project_name)}_交付包.zip"
    package_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(package_path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.write(readable_path, READABLE_NAME)
        archive.write(review_path, REVIEW_NAME)
        archive.write(evidence_path, EVIDENCE_NAME)

    errors = check_package(package_path)
    if errors:
        raise ValueError("; ".join(errors))

    return {
        "status": report["status"],
        "warning_count": report["warning_count"],
        "package_path": str(package_path.resolve()),
        "delivery_files": [str(path.resolve()) for path in (
            readable_path,
            review_path,
            evidence_path,
        )],
        "metrics": report["metrics"],
    }


def check_package(path: Path) -> list[str]:
    errors: list[str] = []
    if not path.is_file():
        return [f"交付包不存在：{path}"]

    try:
        with zipfile.ZipFile(path) as archive:
            names = set(archive.namelist())
            for name in PACKAGE_FILES:
                if name not in names:
                    errors.append(f"缺少交付文件：{name}")
            for name in PACKAGE_FILES:
                if name not in names:
                    continue
                data = archive.read(name)
                if name.endswith(".docx"):
                    errors.extend(
                        f"{name}: {error}"
                        for error in _check_docx_bytes(data)
                    )
                elif name.endswith(".csv"):
                    try:
                        content = data.decode("utf-8-sig")
                    except UnicodeDecodeError as exc:
                        errors.append(f"{name} 不是有效 UTF-8：{exc}")
                        continue
                    if "证据编号" not in content or "事实编号" not in content:
                        errors.append(f"{name} 缺少证据表表头")
    except (OSError, zipfile.BadZipFile) as exc:
        errors.append(f"无法读取交付包：{exc}")

    return errors


def _check_docx_bytes(data: bytes) -> list[str]:
    errors: list[str] = []
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            names = set(archive.namelist())
            for part in sorted(DOCX_REQUIRED_PARTS):
                if part not in names:
                    errors.append(f"缺少 DOCX 部件：{part}")
                elif part.endswith(".xml") or part.endswith(".rels"):
                    try:
                        ElementTree.fromstring(archive.read(part))
                    except ElementTree.ParseError as exc:
                        errors.append(f"{part} XML 无法解析：{exc}")
    except (OSError, zipfile.BadZipFile) as exc:
        errors.append(f"无法读取 DOCX 数据：{exc}")
    return errors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, help="UTF-8 script JSON")
    parser.add_argument("--output-dir", type=Path, help="Directory for three deliverables")
    parser.add_argument("--output", type=Path, help="Optional ZIP output path")
    parser.add_argument("--check", type=Path, help="Check an existing ZIP package")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.check:
            errors = check_package(args.check)
            if errors:
                for error in errors:
                    print(f"ERROR: {error}", file=sys.stderr)
                return 1
            print(
                json.dumps(
                    {"status": "passed", "path": str(args.check.resolve())},
                    ensure_ascii=False,
                )
            )
            return 0
        if not args.input or not args.output_dir:
            print("ERROR: --input and --output-dir are required", file=sys.stderr)
            return 2
        script = load_json(args.input)
        result = build_package(
            script,
            args.output_dir,
            output_zip=args.output,
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
