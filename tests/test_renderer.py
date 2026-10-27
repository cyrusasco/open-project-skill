"""Security and fidelity tests for the canonical offline plan renderer."""
from pathlib import Path
from html.parser import HTMLParser
import copy
import os
import re
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "open-project" / "scripts"
sys.path.insert(0, str(SCRIPTS))
from plan_contract import PacketError, expected_content, packet_digest, sha256
import plan_render
from support import make_packet, save_packet


class Document(HTMLParser):
    def __init__(self, body):
        super().__init__()
        self.tags = []
        self.hrefs = []
        self.feed(body)

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        for key, value in attrs:
            if key == "href":
                self.hrefs.append(value)


class RendererTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT)
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name) / "project"
        self.project.mkdir()
        self.plan = make_packet(self.project)

    def change_draft(self, raw, path=None):
        draft = self.plan["drafts"][0]
        if path is not None:
            draft["path"] = path
        location = self.project / draft["path"]
        location.parent.mkdir(parents=True, exist_ok=True)
        location.write_bytes(raw)
        draft["sha256"] = sha256(raw)
        draft["expected_sha256"] = sha256(expected_content(draft, raw))
        return draft

    def test_all_sections_digest_and_exact_values_are_preserved(self):
        self.plan["facts"] = [
            {"id": "zero", "value": 0, "unit": "jobs", "note": "none observed", "status": "UNVERIFIED"},
            {"id": "fraction", "value": 0.85, "unit": "ratio", "note": "do not round"},
            {"id": "null", "value": None, "note": "not supplied"},
            {"id": "false", "value": False},
        ]
        self.plan["roles"] = [{"name": "zero role", "count": 0, "unit": "sessions"}, {"name": "fraction role", "count": 0.85, "unit": "ratio"}, {"name": "unknown role", "count": None}]
        md, report = plan_render.render_views(self.project, self.plan)
        self.assertEqual((md, report), plan_render.render_views(self.project, copy.deepcopy(self.plan)))
        self.assertIn(packet_digest(self.plan), md)
        self.assertIn(packet_digest(self.plan), report)
        for key, title in plan_render.SECTIONS:
            self.assertIn("## " + title, md)
            self.assertIn('id="' + key + '"', report)
        for value in ["0", "0.85", "null", "false", "jobs", "ratio", "none observed", "UNVERIFIED"]:
            self.assertIn("<td>" + value + "</td>", report)
            self.assertIn(value, md)
        self.assertIn('<span class="count-value">0 sessions</span>', report)
        self.assertIn('<span class="count-value">0.85 ratio</span>', report)
        self.assertIn('style="width:0%"', report)
        self.assertEqual(report.count('class="count-value"'), 2)
        self.assertNotIn("requestAnimationFrame", report)
        self.assertEqual(list((self.project / "md-drafts").glob("PLAN*")), [])

    def test_untrusted_text_is_escaped_and_complete_draft_is_embedded(self):
        original = (self.project / self.plan["drafts"][0]["path"]).read_bytes()
        payload = '</script><img src=x onerror="alert(1)"> & 中文\n````````\nEND OF ENTIRE DRAFT\n'
        draft = self.change_draft(original + payload.encode("utf-8"))
        self.plan["facts"] = [{"name": '<script>alert("x")</script>', "note": "@@CONTENT@@"}]
        md, report = plan_render.render_views(self.project, self.plan)
        document = Document(report)
        self.assertNotIn("script", document.tags)
        self.assertNotIn("img", document.tags)
        self.assertNotIn("iframe", document.tags)
        self.assertIn("&lt;/script&gt;", report)
        self.assertIn("&lt;img src=x onerror=&quot;alert(1)&quot;&gt;", report)
        self.assertIn("END OF ENTIRE DRAFT", report)
        self.assertIn("@@CONTENT@@", report)
        self.assertIn("`````````text", md)
        self.assertIn(draft["sha256"], report)
        self.assertTrue(all(not href.startswith(("http:", "https:", "//", "javascript:")) for href in document.hrefs))

    def test_nested_unicode_draft_links_are_relative_to_report(self):
        original = (self.project / self.plan["drafts"][0]["path"]).read_bytes()
        self.change_draft(original, "md-drafts/nested/中文 draft.DRAFT.md")
        md, report = plan_render.render_views(self.project, self.plan)
        expected = "nested/%E4%B8%AD%E6%96%87%20draft.DRAFT.md"
        self.assertIn('href="' + expected + '"', report)
        self.assertIn("](" + expected + ")", md)
        self.assertNotIn('href="md-drafts/', report)

    def test_relationship_graph_grows_past_thirteen_nodes_and_has_full_tables(self):
        self.plan["graph"] = {
            "status": "UNVERIFIED", "note": "Graph metadata must remain visible",
            "nodes": [{"id": "node" + str(index), "name": "完整 node " + str(index), "kind": "file", "note": "full field " + str(index)} for index in range(18)],
            "links": [{"a": "node0", "b": "node17", "label": "edge <script>", "evidence": "relationship proof"}],
        }
        md, report = plan_render.render_views(self.project, self.plan)
        match = re.search(r'<svg class="graph" viewBox="0 0 800 ([0-9]+)"', report)
        self.assertIsNotNone(match)
        self.assertGreater(int(match.group(1)), 18 * 70)
        for index in range(18):
            self.assertIn("full field " + str(index), report)
            self.assertIn("full field " + str(index), md)
        self.assertIn("Graph metadata must remain visible", report)
        self.assertIn("Graph metadata must remain visible", md)
        self.assertIn("relationship proof", report)
        self.assertIn("Graph links — complete fallback", report)
        self.assertIn("edge &lt;script&gt;", report)

    def test_phase_guide_has_ten_phases_and_accessible_reduced_motion(self):
        md, report = plan_render.render_views(self.project, self.plan)
        self.assertIn('id="workflow"', report)
        self.assertEqual(report.count('class="workflow-phase"'), 10)
        self.assertEqual(report.count('class="phase-pipe"'), 9)
        self.assertIn("these labels do not indicate completion", report)
        self.assertIn("prefers-reduced-motion:reduce", report)
        self.assertIn("animation:phase-flow", report)
        self.assertIn("animation:none!important", report)
        self.assertIn('viewBox="0 0 800 240"', report)
        for index in range(10):
            self.assertIn("Phase " + str(index) + ":", report)
            self.assertIn("Phase " + str(index) + ":", md)
        # Nodes occupy exactly two rows, with five nodes in each row.
        cards = re.findall(r'class="phase-card" x="[0-9]+" y="([0-9]+)"', report)
        self.assertEqual(cards.count("32"), 5)
        self.assertEqual(cards.count("144"), 5)
    def test_cli_changes_only_two_fixed_views_and_is_byte_deterministic(self):
        save_packet(self.project, self.plan)
        before = {path.relative_to(self.project).as_posix(): path.read_bytes() for path in self.project.rglob("*") if path.is_file()}
        result = subprocess.run([sys.executable, str(SCRIPTS / "render-plan.py"), str(self.project)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        after = {path.relative_to(self.project).as_posix(): path.read_bytes() for path in self.project.rglob("*") if path.is_file()}
        self.assertEqual(set(after) - set(before), set(plan_render.OUTPUTS))
        for relative, raw in before.items():
            self.assertEqual(raw, after[relative])
        expected = plan_render.render_views(self.project, self.plan)
        for relative, text in zip(plan_render.OUTPUTS, expected):
            self.assertEqual(after[relative], text.encode("utf-8"))
        self.assertEqual(plan_render.main([str(self.project)]), 0)
        for relative in plan_render.OUTPUTS:
            self.assertEqual(after[relative], (self.project / relative).read_bytes())
        self.assertEqual(list((self.project / "md-drafts").glob(".plan-*.tmp")), [])

    def test_bad_packet_or_draft_does_not_overwrite_existing_views(self):
        for relative in plan_render.OUTPUTS:
            (self.project / relative).write_bytes(b"existing review")
        path = self.project / self.plan["drafts"][0]["path"]
        path.write_bytes(path.read_bytes() + b"tamper")
        with self.assertRaises(PacketError):
            plan_render.write_views(self.project, self.plan)
        for relative in plan_render.OUTPUTS:
            self.assertEqual((self.project / relative).read_bytes(), b"existing review")
        self.plan["revision"] = 0
        save_packet(self.project, self.plan)
        result = subprocess.run([sys.executable, str(SCRIPTS / "render-plan.py"), str(self.project)], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(list((self.project / "md-drafts").glob(".plan-*.tmp")), [])

    def test_output_directory_is_rejected_before_writes(self):
        (self.project / plan_render.OUTPUTS[1]).mkdir()
        with self.assertRaises(PacketError):
            plan_render.write_views(self.project, self.plan)
        self.assertFalse((self.project / plan_render.OUTPUTS[0]).exists())

    def test_output_symlink_is_rejected_even_when_target_is_inside(self):
        target = self.project / "owned-review.md"
        target.write_bytes(b"do not alter")
        output = self.project / plan_render.OUTPUTS[0]
        try:
            output.symlink_to(target)
        except (OSError, NotImplementedError) as exc:
            self.skipTest("symlink creation unavailable: " + str(exc))
        with self.assertRaises(PacketError):
            plan_render.write_views(self.project, self.plan)
        self.assertEqual(target.read_bytes(), b"do not alter")
        self.assertFalse((self.project / plan_render.OUTPUTS[1]).exists())

    def test_second_publish_failure_restores_both_existing_views(self):
        for relative in plan_render.OUTPUTS:
            (self.project / relative).write_bytes(b"previous review")
        original_replace = os.replace
        count = 0
        def fail_second(source, destination):
            nonlocal count
            count += 1
            if count == 2:
                raise OSError("simulated second-view publish failure")
            return original_replace(source, destination)
        with mock.patch.object(plan_render.os, "replace", side_effect=fail_second):
            with self.assertRaises(OSError):
                plan_render.write_views(self.project, self.plan)
        for relative in plan_render.OUTPUTS:
            self.assertEqual((self.project / relative).read_bytes(), b"previous review")
        self.assertEqual(list((self.project / "md-drafts").glob(".plan-*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
