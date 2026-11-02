"""Truthful offline presentation of workflow obligations and evidence."""
from html.parser import HTMLParser
from pathlib import Path
import copy
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills/open-project/scripts"))
import plan_render


class Tags(HTMLParser):
    def __init__(self, value):
        super().__init__()
        self.tags = []
        self.feed(value)

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)


def contract(host="zcode"):
    return {
        "host": host,
        "workflow": {
            "roots": {"docs_root": "C:/new-governance", "destination_mode": "new_folder",
                      "source_roots": [{"id": "code", "path": "D:/old-code"}],
                      "creation_receipt": {"status": "CREATED", "before": "NOT_EXISTS"}},
            "documents": [{"role": "project_manual", "draft_id": "manual",
                           "sections": [{"id": "sop", "heading": "Operating rules"}]}],
            "phases": [{"id": 5, "status": "PROMOTED", "required": True,
                        "evidence": ["promotion-receipt"], "reason": "Writes only"},
                       {"id": 8, "status": "NOT_RUN", "required": True,
                        "evidence": [], "reason": "Independent review pending"}],
            "discovery": {"status": "PARTIAL", "inventory": [{"id": "all-sessions", "total": 815}],
                          "queries": ["project alias"], "receipts": [{"path": "discovery.json", "sha256": "a" * 64}],
                          "reads": [{"id": "session-x", "depth": "summary-only", "fraction": 0.85,
                                     "unread_parts": 0, "remaining": None}],
                          "limitations": ["WAL copy is not an atomic source snapshot"]},
            "features": [{"id": "f1", "requirement_id": "r1", "acceptance": "Observable behavior"}],
            "decisions": {"events": [{"action_id": "A7", "state": "APPROVED", "ref": "user-turn-1"}],
                          "current": [{"action_id": "A7", "state": "APPROVED"}]},
            "review": {"status": "PENDING", "revision": "5", "reviewer_id": None,
                       "author_id": "coordinator", "snapshot_sha256": None,
                       "areas": [], "changed_ids": ["docs-root"], "affected_areas": ["paths"]},
            "package": {"mode": "local_adapter", "status": "PACKAGED", "root": "plugin",
                        "reason": "External local docs are declared",
                        "inventory": [{"role": "manual", "disposition": "external", "root_id": "docs"}],
                        "fresh_session_evidence": []},
            "evidence_policy": {"authorized": False, "allowed_types": [], "prefix_sha256": None},
            "gitnexus": {"applicability": "N/A" if host == "zcode" else "REQUIRED",
                         "tool_id": None if host == "zcode" else "gitnexus-project-onboarding",
                         "reason": "Host-specific contract"},
        },
    }


class WorkflowRendererTests(unittest.TestCase):
    def test_real_v2_packet_has_exact_offline_views_for_both_hosts(self):
        from workflow_support import make_workflow_packet
        from plan_contract import packet_digest
        for host in ("zcode", "codex"):
            with self.subTest(host=host), tempfile.TemporaryDirectory(dir=ROOT) as temporary:
                project = Path(temporary)
                packet = make_workflow_packet(project, host=host)
                self.assertEqual(packet["schema_version"], "2.0")
                expected = plan_render.render_views(project, packet)
                self.assertEqual(expected, plan_render.render_views(project, copy.deepcopy(packet)))
                destinations = plan_render.write_views(project, packet)
                for path, body in zip(destinations, expected):
                    self.assertEqual(path.read_bytes(), body.encode("utf-8"))
                    self.assertIn(packet_digest(packet), body)
                    for role in ("project_manual", "specification", "project_status", "memory", "independent_review"):
                        self.assertIn(role, body)
                self.assertEqual(len(packet["workflow"]["documents"]), 5)
                self.assertIn('href="#workflow-contract"', expected[1])
                for _, heading in plan_render.SECTIONS:
                    self.assertIn("## " + heading, expected[0])
                self.assertIn("NOT_EVALUATED", expected[1])

    def test_every_workflow_category_and_nested_evidence_remain_visible(self):
        md, report = plan_render._workflow_contract(contract())
        for key, heading in plan_render.WORKFLOW_LABELS:
            self.assertIn(heading, md)
            self.assertIn(heading, report)
        for value in ("C:/new-governance", "D:/old-code", "new_folder", "project_manual",
                      "summary-only", "0.85", "null", "all-sessions", "815", "A7",
                      "APPROVED", "PENDING", "local_adapter", "external", "fresh_session_evidence"):
            self.assertIn(value, md)
            self.assertIn(value, report)
        self.assertIn("not an atomic source snapshot", report)

    def test_promotion_and_recorded_counts_never_become_completion(self):
        md, report = plan_render._workflow_contract(contract())
        self.assertIn("PROMOTED", report)
        self.assertIn("NOT_RUN", report)
        self.assertIn("Independent review pending", report)
        self.assertIn("Recorded document mappings", report)
        self.assertIn("<td>1</td>", report)
        self.assertIn("<td>2</td>", report)
        self.assertIn("NOT_EVALUATED", md)
        self.assertIn("NOT_EVALUATED", report)
        self.assertIn("No gate result, approval, independent review or completion is inferred", report)
        self.assertNotIn("<td>COMPLETE</td>", report)

    def test_zcode_does_not_require_gitnexus_but_codex_exposes_it(self):
        z_md, z_html = plan_render._workflow_contract(contract("zcode"))
        c_md, c_html = plan_render._workflow_contract(contract("codex"))
        for value in (z_md, z_html):
            self.assertIn("ZCode: GitNexus is NOT_APPLICABLE", value)
            self.assertIn("absence does not block ZCode completion", value)
        for value in (c_md, c_html):
            self.assertIn("authoritative G6 tool row", value)
            self.assertIn("Fixture results do not establish real-project onboarding", value)
            self.assertIn("gitnexus-project-onboarding", value)
            self.assertNotIn("ZCode: GitNexus is NOT_APPLICABLE", value)

    def test_nested_strings_and_field_names_cannot_become_active_html(self):
        plan = contract()
        plan["workflow"]["review"]["changed_ids"] = ["</table><script>alert(1)</script>"]
        plan["workflow"]["evidence_policy"]["<img src=x onerror=alert(1)>"] = {"nested": "@@CONTENT@@ & 中文"}
        md, report = plan_render._workflow_contract(plan)
        self.assertNotIn("script", Tags(report).tags)
        self.assertNotIn("img", Tags(report).tags)
        self.assertIn("&lt;script&gt;", report)
        self.assertIn("&lt;img", report)
        self.assertIn("@@CONTENT@@ &amp; 中文", report)
        self.assertIn("@@CONTENT@@", md)

    def test_object_order_does_not_change_rendered_contract(self):
        plan = contract()
        reordered = copy.deepcopy(plan)
        reordered["workflow"] = dict(reversed(list(reordered["workflow"].items())))
        reordered["workflow"]["roots"] = dict(reversed(list(reordered["workflow"]["roots"].items())))
        self.assertEqual(plan_render._workflow_contract(plan), plan_render._workflow_contract(reordered))

    def test_legacy_output_cannot_suggest_actionable_ready(self):
        md, report = plan_render._workflow_contract({"host": "zcode"})
        self.assertIn("LEGACY_DIAGNOSTIC", md)
        self.assertIn("Rendering does not establish PLAN_READY or COMPLETE", report)

    def test_unrecognized_nested_extension_is_visible_without_markup_execution(self):
        plan = contract()
        plan["workflow"]["future_extension"] = {"one": {"two": {"three": {"four": "retained-full-value"}}}}
        md, report = plan_render._workflow_contract(plan)
        self.assertIn("Additional workflow field: future_extension", report)
        self.assertIn("retained-full-value", md)
        self.assertIn("retained-full-value", report)


if __name__ == "__main__":
    unittest.main()
