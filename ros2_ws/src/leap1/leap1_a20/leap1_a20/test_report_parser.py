from __future__ import annotations

from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET
from zipfile import ZipFile


DOCX_NAMESPACE = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}


def parse_docx_tables(docx_path: Path) -> list[list[list[str]]]:
    with ZipFile(docx_path) as zf:
        xml = zf.read("word/document.xml")

    root = ET.fromstring(xml)
    tables: list[list[list[str]]] = []
    for table in root.findall(".//w:tbl", DOCX_NAMESPACE):
        table_rows: list[list[str]] = []
        for row in table.findall("./w:tr", DOCX_NAMESPACE):
            cells: list[str] = []
            for cell in row.findall("./w:tc", DOCX_NAMESPACE):
                texts = [node.text or "" for node in cell.findall(".//w:t", DOCX_NAMESPACE)]
                cells.append("".join(texts).strip())
            if any(cell for cell in cells):
                table_rows.append(cells)
        if table_rows:
            tables.append(table_rows)
    return tables


def _row_payload(category: str, item: str, focus: str, record: str, source: str) -> dict[str, str]:
    return {
        "category": category,
        "item": item,
        "focus": focus,
        "record": record,
        "source": source,
    }


def build_broadcast_center_summary(docx_path: Path) -> dict[str, Any]:
    tables = parse_docx_tables(docx_path)
    rows: list[dict[str, str]] = []

    def append_table_rows(
        table_index: int,
        category: str,
        *,
        item_idx: int,
        focus_builder,
        record_builder,
        source_label: str,
        limit: int | None = None,
    ) -> None:
        if table_index >= len(tables):
            return
        data_rows = tables[table_index][1:]
        if limit is not None:
            data_rows = data_rows[:limit]
        for row in data_rows:
            if item_idx >= len(row) or not row[item_idx].strip():
                continue
            rows.append(
                _row_payload(
                    category=category,
                    item=row[item_idx].strip(),
                    focus=focus_builder(row).strip(),
                    record=record_builder(row).strip(),
                    source=source_label,
                )
            )

    append_table_rows(
        20,
        "广播中心展示",
        item_idx=0,
        focus_builder=lambda row: f"显示内容: {row[2]} | 刷新频率: {row[3]}",
        record_builder=lambda row: f"测试结果: {row[4]}",
        source_label="表21",
    )
    append_table_rows(
        21,
        "状态上报可靠性",
        item_idx=0,
        focus_builder=lambda row: f"测试时长: {row[1]} | 实收/应发: {row[3]}/{row[2]}",
        record_builder=lambda row: f"丢失率: {row[4]} | 错误率: {row[5]} | 结论: {row[6]}",
        source_label="表22",
    )
    append_table_rows(
        22,
        "全链路联动",
        item_idx=0,
        focus_builder=lambda row: f"发现火源: {row[3]} | 广播上报: {row[6]} | 总耗时: {row[7]}",
        record_builder=lambda row: f"是否成功: {row[8]} | 备注: {row[9] if len(row) > 9 else ''}",
        source_label="表23",
        limit=3,
    )
    append_table_rows(
        23,
        "异常保护",
        item_idx=0,
        focus_builder=lambda row: f"系统响应: {row[2]} | 守护动作: {row[3]}",
        record_builder=lambda row: f"是否通过: {row[4]}",
        source_label="表24",
    )
    append_table_rows(
        26,
        "核心验收指标",
        item_idx=1,
        focus_builder=lambda row: f"标准要求: {row[2]} | 实测结果: {row[3]}",
        record_builder=lambda row: f"达标状态: {row[4]} | 证据页码: {row[5]}",
        source_label="表27",
    )

    if len(tables) > 12:
        for row in tables[12][1:]:
            if len(row) < 2:
                continue
            key = row[0].strip()
            value = row[1].strip()
            if key in {"水泵型号/流量", "单次喷射时长", "喷射距离"}:
                rows.append(
                    _row_payload(
                        category="灭火执行参数",
                        item=key,
                        focus=f"当前记录值: {value}",
                        record="用于喷射距离/时长/覆盖测试",
                        source="表13",
                    )
                )

    return {
        "docx_path": str(docx_path),
        "row_count": len(rows),
        "rows": rows,
    }
