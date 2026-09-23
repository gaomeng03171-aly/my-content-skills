#!/usr/bin/env python3
"""Deprecated entrypoint that delegates to build_package.py."""

from __future__ import annotations

import argparse
import json
import sys
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

from script_contract import check_docx, load_json, validate_script


W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


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
) -> str:
    properties: list[str] = []
    if style:
        properties.append(f'<w:pStyle w:val="{style}"/>')
    if keep_next:
        properties.append("<w:keepNext/>")
    if align:
        properties.append(f'<w:jc w:val="{align}"/>')
    properties.append(
        f'<w:spacing w:before="{before}" w:after="{after}" w:line="{line}" '
        'w:lineRule="auto"/>'
    )
    paragraph_properties = (
        f"<w:pPr>{''.join(properties)}</w:pPr>" if properties else ""
    )
    return (
        "<w:p>"
        f"{paragraph_properties}"
        f"{_run(text, bold=bold, size=size)}"
        "</w:p>"
    )


def _run(text: str, *, bold: bool = False, size: int | None = None) -> str:
    run_properties = [
        '<w:rFonts w:ascii="Aptos" w:hAnsi="Aptos" w:eastAsia="微软雅黑"/>'
    ]
    if bold:
        run_properties.append("<w:b/>")
    if size:
        run_properties.append(f'<w:sz w:val="{size}"/><w:szCs w:val="{size}"/>')
    content: list[str] = []
    lines = text.split("\n")
    for index, line in enumerate(lines):
        if index:
            content.append("<w:br/>")
        content.append(
            f'<w:t xml:space="preserve">{escape(line)}</w:t>'
        )
    return f"<w:r><w:rPr>{''.join(run_properties)}</w:rPr>{''.join(content)}</w:r>"


def _cell(
    text: str,
    width: int,
    *,
    header: bool = False,
    align: str = "left",
) -> str:
    shading = '<w:shd w:val="clear" w:fill="F2F2F2"/>' if header else ""
    style = "TableHeader" if header else "TableText"
    return (
        "<w:tc>"
        "<w:tcPr>"
        f'<w:tcW w:w="{width}" w:type="dxa"/>'
        f"{shading}"
        '<w:vAlign w:val="center"/>'
        "</w:tcPr>"
        f"{_paragraph(text, style, bold=header, align=align, after=0, line=260)}"
        "</w:tc>"
    )


def _table(
    headers: list[str],
    rows: list[list[str]],
    widths: list[int],
    *,
    table_width: int = 9000,
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
            _cell(text, widths[index], header=True)
            for index, text in enumerate(headers)
        )
        + "</w:tr>"
    )
    body_rows = []
    for row in rows:
        body_rows.append(
            "<w:tr>"
            + "".join(
                _cell(text, widths[index])
                for index, text in enumerate(row)
            )
            + "</w:tr>"
        )
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


def _styles_xml() -> str:
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="{W_NS}">
  <w:docDefaults>
    <w:rPrDefault>
      <w:rPr>
        <w:rFonts w:ascii="Aptos" w:hAnsi="Aptos" w:eastAsia="微软雅黑"/>
        <w:sz w:val="22"/>
        <w:szCs w:val="22"/>
      </w:rPr>
    </w:rPrDefault>
    <w:pPrDefault>
      <w:pPr>
        <w:spacing w:after="120" w:line="340" w:lineRule="auto"/>
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
      <w:rFonts w:ascii="Aptos Display" w:hAnsi="Aptos Display" w:eastAsia="微软雅黑"/>
      <w:b/>
      <w:color w:val="000000"/>
      <w:sz w:val="36"/>
      <w:szCs w:val="36"/>
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
      <w:color w:val="000000"/>
      <w:sz w:val="28"/>
      <w:szCs w:val="28"/>
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
      <w:color w:val="000000"/>
      <w:sz w:val="24"/>
      <w:szCs w:val="24"/>
    </w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="TableText">
    <w:name w:val="Table Text"/>
    <w:basedOn w:val="Normal"/>
    <w:pPr>
      <w:spacing w:before="40" w:after="40" w:line="260" w:lineRule="auto"/>
    </w:pPr>
    <w:rPr>
      <w:sz w:val="20"/>
      <w:szCs w:val="20"/>
    </w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="TableHeader">
    <w:name w:val="Table Header"/>
    <w:basedOn w:val="TableText"/>
    <w:rPr>
      <w:b/>
      <w:color w:val="000000"/>
    </w:rPr>
  </w:style>
</w:styles>
"""


def _core_properties(title: str, date: str, creator: str = "") -> str:
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:dcmitype="http://purl.org/dc/dcmitype/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <dc:title>{escape(title)}</dc:title>
  <dc:creator>{escape(creator)}</dc:creator>
  <cp:lastModifiedBy>{escape(creator)}</cp:lastModifiedBy>
  <dcterms:created xsi:type="dcterms:W3CDTF">{escape(date)}T00:00:00Z</dcterms:created>
  <dcterms:modified xsi:type="dcterms:W3CDTF">{escape(date)}T00:00:00Z</dcterms:modified>
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


def _document_xml(script: dict[str, object]) -> str:
    report = validate_script(script)
    if report["error_count"]:
        details = "; ".join(
            item["message"]
            for item in report["issues"]
            if item["level"] == "error"
        )
        raise ValueError(f"script contract failed: {details}")

    project = script["project"]
    strategy = script["strategy"]
    narration = script["narration"]
    delivery = script["delivery"]
    assert isinstance(project, dict)
    assert isinstance(strategy, dict)
    assert isinstance(narration, dict)
    assert isinstance(delivery, dict)

    project_name = str(project["name"]).strip()
    locations = [str(value).strip() for value in project["locations"]]
    tone = str(project["tone"]).strip()
    duration = float(project["duration_seconds"])
    platform = str(project.get("platform") or "未指定").strip()
    audience = str(project.get("audience") or "通用旅行观众").strip()
    version = str(delivery["version"]).strip()
    date = str(delivery["date"]).strip()
    notes = str(delivery.get("notes") or "").strip()

    parts = [
        _paragraph(
            f"{project_name} 旅游视频文案",
            "Title",
            align="center",
            after=100,
        ),
        _paragraph(
            f"{version} | {date}",
            align="center",
            size=20,
            after=260,
        ),
        _paragraph("项目信息", "Heading1"),
        _table(
            ["项目", "内容"],
            [
                ["旅游地点", "、".join(locations)],
                ["情感基调", tone],
                ["视频时长", f"{duration:g} 秒（约 {duration / 60:.2f} 分钟）"],
                ["发布平台", platform],
                ["目标受众", audience],
                ["交付版本", version],
            ],
            [2200, 6800],
        ),
        _paragraph("创作策略", "Heading1"),
        _paragraph(f"核心主题：{strategy['core_theme']}"),
        _paragraph(f"开场设计：{strategy['opening_angle']}"),
        _paragraph(f"收束设计：{strategy['closing_idea']}"),
        _paragraph("地点职责", "Heading2", keep_next=True),
        _table(
            ["地点", "叙事职责"],
            [
                [str(item["location"]), str(item["role"])]
                for item in strategy["location_roles"]
            ],
            [2400, 6600],
        ),
        _paragraph("情感标记", "Heading2", keep_next=True),
        _paragraph(
            "、".join(str(value) for value in strategy["tone_markers"])
        ),
        _paragraph("标题方案", "Heading1"),
    ]

    for index, title in enumerate(script["titles"], start=1):
        parts.append(_paragraph(f"{index}. {title}"))

    parts.append(_paragraph("完整配音文案", "Heading1"))
    sections = narration["sections"]
    for index, section in enumerate(sections, start=1):
        assert isinstance(section, dict)
        section_locations = "、".join(
            str(value) for value in section["locations"]
        )
        heading = (
            f"{index}. {section['name']} | {float(section['target_seconds']):g} 秒"
        )
        if section_locations:
            heading += f" | {section_locations}"
        parts.append(_paragraph(heading, "Heading2", keep_next=True))
        paragraphs = [
            value.strip()
            for value in str(section["text"]).split("\n")
            if value.strip()
        ]
        parts.extend(_paragraph(value) for value in paragraphs)

    duration_rows: list[list[str]] = []
    for section in sections:
        assert isinstance(section, dict)
        seconds = float(section["target_seconds"])
        percentage = seconds / duration * 100 if duration else 0
        duration_rows.append(
            [
                str(section["name"]),
                f"{seconds:g}",
                f"{percentage:.1f}%",
                "、".join(str(value) for value in section["locations"]),
            ]
        )
    duration_rows.append(
        ["合计", f"{sum(float(item['target_seconds']) for item in sections):g}", "100.0%", ""]
    )
    parts.extend(
        [
            _paragraph("时长分配", "Heading1"),
            _table(
                ["段落", "秒数", "占比", "地点"],
                duration_rows,
                [1800, 1200, 1200, 4800],
            ),
        ]
    )

    if notes:
        parts.extend(
            [
                _paragraph("交付备注", "Heading1"),
                _paragraph(notes),
            ]
        )

    section_properties = (
        "<w:sectPr>"
        '<w:pgSz w:w="11906" w:h="16838"/>'
        '<w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440" '
        'w:header="720" w:footer="720" w:gutter="0"/>'
        "</w:sectPr>"
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<w:document xmlns:w="{W_NS}">'
        f"<w:body>{''.join(parts)}{section_properties}</w:body>"
        "</w:document>"
    )


def build_docx(script: dict[str, object], output: Path) -> None:
    from build_package import build_package

    package_path = (
        output.with_suffix(".zip")
        if output.suffix.lower() == ".docx"
        else output
    )
    build_package(script, output.parent, output_zip=package_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, help="UTF-8 script JSON")
    parser.add_argument("--output", type=Path, help="Destination DOCX")
    parser.add_argument("--check", type=Path, help="Check an existing DOCX")
    return parser.parse_args()


def main() -> int:
    from build_package import main as package_main

    return package_main()


if __name__ == "__main__":
    sys.exit(main())
