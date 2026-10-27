#!/usr/bin/env python3
"""Deterministic, offline review views for open-project plan packets.

Only this module defines the rendered bytes. The review gate imports
``render_views`` and compares those bytes, binding both views to the same packet.
"""
from __future__ import annotations

import argparse
import html
import json
import math
import os
from pathlib import Path
import re
import stat
import sys
import tempfile
from urllib.parse import quote

from plan_contract import PacketError, load_plan, packet_digest, read_draft, resolve_inside, validate_plan

OUTPUTS = ("md-drafts/PLAN.DRAFT.md", "md-drafts/PLAN-REPORT.DRAFT.html")
TEMPLATE = Path(__file__).resolve().parents[1] / "templates" / "plan-report.template.html"
SECTIONS = (
    ("facts", "§1 核實數字快照 / Verified facts"),
    ("unknowns", "§2 未知事項 / Unknowns"),
    ("conflicts", "§3 衝突清單 / Conflicts"),
    ("pains", "§4 痛點排行 / Pain points"),
    ("roles", "§5 角色重複統計 / Roles"),
    ("tools", "§6 工具化評估 / Tools and open source"),
    ("code-map", "§7 Code map"),
    ("drafts", "§8 草稿 manifest / Draft manifest"),
    ("changes", "§9 執行時間線與資料夾變更 / Timeline and folder changes"),
    ("risks", "§10 風險 / Risks"),
    ("requirements", "§11 原始需求與授權 / Requirements and authorization"),
)
EMPTY = "暫無記錄 / No entries. This does not establish verification."


def _text(value: object) -> str:
    """Keep null, false, zero, decimals and every narrative field visible."""
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False, separators=(",", ":"))


def _escape(value: object) -> str:
    return html.escape(_text(value), quote=True)


def _md(value: object) -> str:
    # Escape raw HTML and table boundaries; line breaks are controlled markup.
    text = html.escape(_text(value), quote=False).replace("\\", "\\\\")
    for punctuation in ("`", "[", "]", "|"):
        text = text.replace(punctuation, "\\" + punctuation)
    return text.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "<br>")


def _rows(items: object) -> list[dict]:
    if items is None:
        return [{"value": None}]
    if isinstance(items, dict):
        return [items]
    if not isinstance(items, list):
        return [{"value": items}]
    return [item if isinstance(item, dict) else {"value": item} for item in items]


def _columns(rows: list[dict]) -> list[str]:
    keys = {key for row in rows for key in row}
    preferred = ("id", "name", "label", "description", "value", "unit", "status", "note", "path", "target", "template", "kind", "required", "sha256", "baseline_sha256", "expected_sha256", "transforms", "depends_on")
    return [key for key in preferred if key in keys] + sorted(keys.difference(preferred))


def _table(items: object, caption: str) -> tuple[str, str]:
    rows = _rows(items)
    if not rows:
        return EMPTY + "\n", '<p class="empty">' + html.escape(EMPTY) + "</p>"
    cols = _columns(rows)
    # A deliberately empty object still needs a visible representation.
    if not cols:
        rows, cols = [{"value": {}} for row in rows], ["value"]
    md = "| " + " | ".join(_md(col) for col in cols) + " |\n"
    md += "| " + " | ".join("---" for _ in cols) + " |\n"
    rendered = []
    for row in rows:
        # Missing and explicit null are distinct. A missing field is an em dash.
        md += "| " + " | ".join(_md(row[col]) if col in row else "—" for col in cols) + " |\n"
        rendered.append("<tr>" + "".join("<td>" + (_escape(row[col]) if col in row else "—") + "</td>" for col in cols) + "</tr>")
    markup = '<div class="table-scroll" tabindex="0" role="region" aria-label="' + html.escape(caption, quote=True) + '"><table><caption>' + html.escape(caption) + '</caption><thead><tr>'
    markup += "".join('<th scope="col">' + html.escape(col) + "</th>" for col in cols)
    markup += "</tr></thead><tbody>" + "".join(rendered) + "</tbody></table></div>"
    return md, markup


def _relative_href(relative: str) -> str:
    # The report lives in md-drafts, so md-drafts/x is linked as x, not md-drafts/x.
    clean = relative.replace("\\", "/")
    parts = clean.split("/")
    report_parts = ["md-drafts"]
    while parts and report_parts and parts[0] == report_parts[0]:
        parts.pop(0)
        report_parts.pop(0)
    return quote("../" * len(report_parts) + "/".join(parts), safe="/-._~")


def _draft_text(project: Path, draft: dict) -> str:
    try:
        return read_draft(project, draft).decode("utf-8")
    except UnicodeError as exc:
        raise PacketError("draft must be UTF-8 text: " + draft["path"]) from exc


def _fence(text: str) -> str:
    runs = [len(value) for value in re.findall(r"`+", text)]
    return "`" * max(3, 1 + max(runs, default=0))


def _drafts(project: Path, drafts: list[dict]) -> tuple[str, str]:
    md, markup = _table(drafts, "Draft manifest — hashes and complete metadata")
    for index, draft in enumerate(drafts, 1):
        body = _draft_text(project, draft)
        fence = _fence(body)
        href = _relative_href(draft["path"])
        md += "\n### Draft " + str(index) + ": " + _md(draft["id"]) + "\n\n"
        md += "[" + _md(draft["path"]) + "](" + href + ")\n\n"
        md += fence + "text\n" + body + ("" if body.endswith("\n") else "\n") + fence + "\n"
        markup += '<article class="draft" aria-labelledby="draft-' + str(index) + '"><h3 id="draft-' + str(index) + '">Draft ' + str(index) + ": " + _escape(draft["id"]) + '</h3><p><a href="' + html.escape(href, quote=True) + '">Open ' + _escape(draft["path"]) + '</a></p><pre class="draft-text" tabindex="0"><code>' + html.escape(body, quote=True) + "</code></pre></article>"
    return md, markup


def _count_bars(items: object, caption: str) -> str:
    """Display only recorded finite counts; keep their exact text beside each bar."""
    if not isinstance(items, list):
        return ""
    measured = [row for row in items if isinstance(row, dict) and type(row.get("count")) in (int, float) and (type(row["count"]) is int or math.isfinite(row["count"])) and row["count"] >= 0]
    if not measured:
        return ""
    largest = max(row["count"] for row in measured)
    parts = ['<div class="count-chart"><p class="chart-note">Recorded counts; verification states, units and notes remain in the complete table below.</p><ul aria-label="' + html.escape(caption, quote=True) + '">']
    for index, row in enumerate(measured, 1):
        label = row.get("name", row.get("label", row.get("id", "Row " + str(index))))
        width = row["count"] / largest * 100 if largest else 0
        width_text = format(width, ".6f").rstrip("0").rstrip(".") or "0"
        value = _escape(row["count"]) + ((" " + _escape(row["unit"])) if "unit" in row else "")
        parts.append('<li><span class="count-label">' + _escape(label) + '</span><span class="count-track" aria-hidden="true"><span class="count-fill" style="width:' + width_text + '%"></span></span><span class="count-value">' + value + '</span></li>')
    parts.append('</ul></div>')
    return "".join(parts)

PHASES = (
    "Intent / 意圖", "Facts / 事實", "Sessions / 對話", "Files / 檔案", "PLAN + drafts / 草稿",
    "Promote / 升格", "Implement / 實作", "Plugin / 插件", "Review / 審核", "Handover / 交接",
)


def _workflow() -> tuple[str, str]:
    """A process guide, explicitly independent of execution or completion state."""
    md = "## Process guide — Phase 0–9\n\nProcess guide only; these labels do not indicate completion.\n\n"
    md += "".join(str(index + 1) + ". Phase " + str(index) + ": " + label + "\n" for index, label in enumerate(PHASES)) + "\n"
    parts = ['<section id="workflow" aria-labelledby="workflow-title"><h2 id="workflow-title">Process guide — Phase 0–9</h2><p>Process guide only; these labels do not indicate completion. No phase status is inferred from rendering.</p><div class="graph-scroll"><svg class="workflow-visual" viewBox="0 0 800 240" width="800" height="240" role="img" aria-labelledby="phase-title phase-desc"><title id="phase-title">Phase 0–9 process guide</title><desc id="phase-desc">Read left to right across the first row, then right to left across the second row. This is a process guide, not a completion record. A text sequence follows.</desc><defs><marker id="phase-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse"><path class="phase-arrow" d="M0 0 L10 5 L0 10 Z"/></marker></defs>']
    positions = [(14 + index * 158, 32) for index in range(5)] + [(14 + (9 - index) * 158, 144) for index in range(5, 10)]
    for index in range(9):
        x, y = positions[index]
        nx, ny = positions[index + 1]
        if index == 4:
            path = "M" + str(x + 70) + " " + str(y + 64) + " V" + str(ny)
        elif index < 4:
            path = "M" + str(x + 140) + " " + str(y + 32) + " H" + str(nx)
        else:
            path = "M" + str(x) + " " + str(y + 32) + " H" + str(nx + 140)
        parts.append('<path class="phase-pipe" d="' + path + '" marker-end="url(#phase-arrow)"/>')
    for index, (label, (x, y)) in enumerate(zip(PHASES, positions)):
        english, chinese = label.split(" / ", 1)
        parts.append('<g class="workflow-phase"><rect class="phase-card" x="' + str(x) + '" y="' + str(y) + '" width="140" height="64" rx="7"/><text class="phase-number" x="' + str(x + 10) + '" y="' + str(y + 20) + '">Phase ' + str(index) + '</text><text class="phase-label" x="' + str(x + 10) + '" y="' + str(y + 44) + '">' + html.escape(english) + ' / ' + html.escape(chinese) + '</text></g>')
    parts.append('</svg></div><details class="workflow-text"><summary>Phase 0–9 text sequence</summary><ol class="workflow-sequence">')
    parts.extend('<li>Phase ' + str(index) + ': ' + html.escape(label) + '</li>' for index, label in enumerate(PHASES))
    parts.append('</ol></details></section>')
    return md, "".join(parts)

def _graph(graph: object) -> tuple[str, str]:
    if graph is None or graph == {}:
        return "", ""
    if not isinstance(graph, dict) or not graph.get("nodes"):
        fallback_md, fallback_html = _table(graph, "Relationship data — no nodes supplied")
        return "\n## Relationships\n\n" + fallback_md, '<section id="relationships"><h2>Relationships</h2>' + fallback_html + "</section>"
    nodes = graph["nodes"]
    links = graph.get("links", [])
    if not isinstance(nodes, list) or any(not isinstance(node, dict) for node in nodes):
        raise PacketError("graph.nodes must contain objects")
    if not isinstance(links, list) or any(not isinstance(link, dict) for link in links):
        raise PacketError("graph.links must contain objects")
    md_nodes, html_nodes = _table(nodes, "Graph nodes — complete fallback")
    md_links, html_links = _table(links, "Graph links — complete fallback")
    # One node per row avoids crowded horizontal layouts and grows beyond 13 nodes.
    height = max(180, 76 * len(nodes) + 40)
    positions = {str(node.get("id", index)): (34, 46 + index * 76) for index, node in enumerate(nodes)}
    parts = ['<div class="graph-scroll"><svg class="graph" viewBox="0 0 800 ' + str(height) + '" width="800" height="' + str(height) + '" role="img" aria-labelledby="graph-title graph-desc"><title id="graph-title">Plan relationships</title><desc id="graph-desc">' + str(len(nodes)) + ' nodes. Complete node and relationship tables follow this diagram.</desc>']
    for link in links:
        start = positions.get(str(link.get("a", link.get("source", ""))))
        end = positions.get(str(link.get("b", link.get("target", ""))))
        if start and end:
            parts.append('<path class="edge" d="M34 ' + str(start[1]) + ' C8 ' + str(start[1]) + ' 8 ' + str(end[1]) + ' 34 ' + str(end[1]) + '"/>')
    for index, node in enumerate(nodes):
        x, y = positions[str(node.get("id", index))]
        label = _text(node.get("name", node.get("label", node.get("id", index))))
        # Full labels remain present in title and the table; visible labels wrap.
        parts.append('<g><title>' + html.escape(label) + '</title><circle class="graph-node" cx="' + str(x) + '" cy="' + str(y) + '" r="8"/><text x="56" y="' + str(y - 9) + '">')
        wrapped = [label[pos:pos + 58] for pos in range(0, min(len(label), 116), 58)] or [""]
        for line_index, line in enumerate(wrapped):
            parts.append('<tspan x="56" dy="' + ("0" if line_index == 0 else "19") + '">' + html.escape(line) + ("…" if line_index == len(wrapped) - 1 and len(label) > 116 else "") + '</tspan>')
        parts.append('</text></g>')
    parts.append('</svg></div>')
    metadata = {key: value for key, value in graph.items() if key not in ("nodes", "links")}
    extra_md, extra_html = _table(metadata, "Relationship metadata") if metadata else ("", "")
    markup = '<section id="relationships"><h2>Relationships</h2>' + "".join(parts) + html_nodes + html_links + extra_html + '</section>'
    return "\n## Relationships\n\n" + md_nodes + "\n" + md_links + "\n" + extra_md, markup


def _safe_template(values: dict[str, str]) -> str:
    template = TEMPLATE.read_text(encoding="utf-8")
    markers = re.findall(r"@@([A-Z_]+)@@", template)
    if set(markers) != set(values) or any(markers.count(key) != 1 for key in values):
        raise PacketError("renderer template has unexpected or duplicate placeholders")
    # One substitution pass prevents packet text from becoming a template instruction.
    return re.sub(r"@@([A-Z_]+)@@", lambda match: values[match.group(1)], template)


def render_views(project: Path, plan: dict) -> tuple[str, str]:
    """Return exact UTF-8 Markdown/HTML strings without writing or using a clock."""
    validate_plan(plan)
    project = Path(project)
    digest = packet_digest(plan)
    title = _text(plan["project"]["name"]) + " — PLAN review draft"
    metadata = {key: plan[key] for key in ("schema_version", "plan_id", "revision", "host", "project", "route", "scale")}
    md_meta, html_meta = _table(metadata, "Packet identity and scope")
    md = "# " + _md(title) + "\n\n> DRAFT — review does not authorize promotion or execution.\n\n"
    md += "> Recorded evidence snapshot. Rendering does not revalidate current source bytes; run the gate before approval or promotion.\n\n"
    md += "Packet SHA-256: `" + digest + "`\n\n" + md_meta + "\n"
    workflow_md, workflow_html = _workflow()
    md += workflow_md
    content = [workflow_html]
    for key, heading in SECTIONS:
        if key == "code-map":
            items = plan.get("code_map", [{"status": "UNVERIFIED", "note": "No code map supplied in this packet."}])
        elif key == "changes":
            items = plan["folder_changes"]
        else:
            items = plan[key]
        if key == "drafts":
            section_md, section_html = _drafts(project, items)
        else:
            section_md, section_html = _table(items, heading)
        if key in ("pains", "roles"):
            section_html = _count_bars(items, heading) + section_html
        if key == "facts":
            sources_md, sources_html = _table(plan["sources"], "Sources — paths, checksums and provenance")
            section_md += "\n### Sources\n\n" + sources_md
            section_html += '<h3>Sources and provenance</h3>' + sources_html
        if key == "tools":
            oss_md, oss_html = _table(plan["oss"], "Open-source candidates")
            section_md += "\n### Open-source candidates\n\n" + oss_md
            section_html += '<h3>Open-source candidates</h3>' + oss_html
        if key == "changes" and "timeline" in plan:
            timeline_md, timeline_html = _table(plan["timeline"], "Timeline")
            section_md += "\n### Timeline\n\n" + timeline_md
            section_html += '<h3>Timeline</h3>' + timeline_html
        if key == "requirements" and "approval_requests" in plan:
            approvals_md, approvals_html = _table(plan["approval_requests"], "Explicit authorization requests and state")
            section_md += "\n### Authorization state\n\n" + approvals_md
            section_html += '<h3>Authorization state</h3>' + approvals_html
        md += "## " + heading + "\n\n" + section_md + "\n"
        content.append('<section id="' + key + '"><h2>' + html.escape(heading) + '</h2>' + section_html + '</section>')
    graph_md, graph_html = _graph(plan.get("graph"))
    md += graph_md
    content.append(graph_html)
    # Include all extension metadata rather than silently dropping approved fields.
    handled = set(metadata) | {key for key, _ in SECTIONS} | {"folder_changes", "sources", "oss", "graph", "code_map", "timeline", "approval_requests"}
    extensions = {key: plan[key] for key in sorted(set(plan) - handled)}
    if extensions:
        extra_md, extra_html = _table(extensions, "Additional packet metadata")
        md += "\n## Additional packet metadata\n\n" + extra_md
        content.append('<section id="metadata"><h2>Additional packet metadata</h2>' + extra_html + '</section>')
    toc = '<nav aria-label="Report sections"><ol>' + "".join('<li><a href="#' + key + '">' + html.escape(heading) + '</a></li>' for key, heading in SECTIONS) + '</ol></nav>'
    markup = _safe_template({"TITLE": html.escape(title, quote=True), "HEADER": html.escape(title, quote=True), "DIGEST": digest, "META": html_meta, "TOC": toc, "CONTENT": "\n".join(content)})
    return md.rstrip() + "\n", markup.rstrip() + "\n"


def _output_path(project: Path, relative: str) -> Path:
    path = resolve_inside(project, relative)
    base = project.resolve(strict=True)
    # Also reject links pointing inside the project: they hide the actual output file.
    cursor = base
    for part in Path(relative).parts:
        cursor = cursor / part
        try:
            info = cursor.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or bool(getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)):
            raise PacketError("unsafe symlink/reparse output: " + relative)
    if path.exists() and not path.is_file():
        raise PacketError("output is not a regular file: " + relative)
    if not path.parent.is_dir():
        raise PacketError("output directory does not exist: " + relative)
    return path


def write_views(project: Path, plan: dict) -> tuple[Path, Path]:
    """Validate and stage both views before replacing either fixed output."""
    md, markup = render_views(project, plan)
    destinations = [_output_path(project, relative) for relative in OUTPUTS]
    originals = [path.read_bytes() if path.exists() else None for path in destinations]
    staged: list[Path] = []
    replaced: list[int] = []
    try:
        for destination, body in zip(destinations, (md, markup)):
            descriptor, filename = tempfile.mkstemp(prefix=".plan-render-", suffix=".tmp", dir=destination.parent)
            temporary = Path(filename)
            staged.append(temporary)
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(body.encode("utf-8"))
                stream.flush()
                os.fsync(stream.fileno())
        # Recheck after staging to catch changed links before publishing views.
        for relative in OUTPUTS:
            _output_path(project, relative)
        for index, (temporary, destination) in enumerate(zip(staged, destinations)):
            os.replace(temporary, destination)
            replaced.append(index)
    except BaseException:
        for index in reversed(replaced):
            destination, original = destinations[index], originals[index]
            if original is None:
                destination.unlink(missing_ok=True)
            else:
                descriptor, filename = tempfile.mkstemp(prefix=".plan-restore-", suffix=".tmp", dir=destination.parent)
                temporary = Path(filename)
                staged.append(temporary)
                with os.fdopen(descriptor, "wb") as stream:
                    stream.write(original)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temporary, destination)
        raise
    finally:
        for temporary in staged:
            temporary.unlink(missing_ok=True)
    return destinations[0], destinations[1]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render offline PLAN review drafts from md-drafts/plan-data.json")
    parser.add_argument("project", type=Path, help="project root (only two fixed draft views are written)")
    args = parser.parse_args(argv)
    try:
        plan = load_plan(args.project)
        write_views(args.project, plan)
    except (PacketError, OSError, ValueError, TypeError) as exc:
        print("FAIL: " + str(exc), file=sys.stderr)
        return 2
    print("RENDERED: " + ", ".join(OUTPUTS))
    return 0
