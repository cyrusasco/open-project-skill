"""Deterministic synthetic fixtures shared by renderer, gate and promotion tests."""
import hashlib
import json
from pathlib import Path


def make_packet(project, host="zcode"):
    from plan_contract import DRAFT_MARKER, expected_content
    project = Path(project)
    staging = project / "md-drafts"
    staging.mkdir(parents=True, exist_ok=True)
    marker = DRAFT_MARKER.decode("utf-8") if isinstance(DRAFT_MARKER, bytes) else DRAFT_MARKER
    raw = (marker + "\n# Specification\r\n\r\nSynthetic product behavior for fixture tests.\r\n").encode("utf-8")
    draft = {"id": "spec", "path": "md-drafts/product_specification.DRAFT.md",
             "target": "product_specification.md", "template": "product_specification.template.md",
             "kind": "specification", "required": True, "sha256": hashlib.sha256(raw).hexdigest(),
             "baseline_sha256": "NOT_EXISTS", "expected_sha256": "0" * 64,
             "transforms": ["remove_draft_marker", "normalize_utf8_lf"]}
    (project / draft["path"]).write_bytes(raw)
    draft["expected_sha256"] = hashlib.sha256(expected_content(draft, raw)).hexdigest()
    packet = {"schema_version": "1.0", "plan_id": "test-plan", "revision": "1", "host": host,
              "project": {"name": "Synthetic"}, "route": "reorg", "scale": "M", "drafts": [draft]}
    for key in ("facts", "unknowns", "conflicts", "pains", "roles", "tools", "oss", "sources",
                "folder_changes", "risks", "requirements", "code_map", "timeline", "approval_requests"):
        packet[key] = []
    return packet


def save_packet(project, packet):
    staging = Path(project) / "md-drafts"
    staging.mkdir(parents=True, exist_ok=True)
    path = staging / "plan-data.json"
    path.write_text(json.dumps(packet, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    return path
