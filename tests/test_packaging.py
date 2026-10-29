from pathlib import Path
import importlib.util
import json
import shutil
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("open_project_build", ROOT / "scripts/build-plugin.py")
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)

class PackagingTests(unittest.TestCase):
    def test_build_exact_resources_and_noop(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as td:
            output = Path(td) / "package"
            result = builder.build(ROOT, output)
            self.assertEqual(result["status"], "PACKAGED")
            self.assertFalse(result["installation_verified"])
            self.assertTrue((output / "LICENSE").is_file())
            self.assertTrue((output / "skills/open-project/SKILL.md").is_file())
            self.assertFalse((output / ".git").exists())
            self.assertFalse((output / "tests").exists())
            self.assertFalse((output / "README.md").exists())
            self.assertEqual(builder.build(ROOT, output)["build"], "NO_OP")
            for item in result["files"]:
                self.assertEqual(builder.digest((output / item["path"]).read_bytes()), item["sha256"])

    def test_different_existing_package_is_not_overwritten(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as td:
            output = Path(td) / "package"
            builder.build(ROOT, output)
            file = output / "skills/open-project/SKILL.md"
            file.write_text("user edit", encoding="utf-8")
            with self.assertRaises(ValueError):
                builder.build(ROOT, output)
            self.assertEqual(file.read_text(encoding="utf-8"), "user edit")

    def test_source_directory_cannot_be_output(self):
        with self.assertRaises(ValueError):
            builder.build(ROOT, ROOT / "skills/open-project")

    def test_unexpected_private_resource_is_rejected(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as td:
            root = Path(td) / "source"
            root.mkdir()
            for rel in ["LICENSE", "VERSION", "SOURCE.json", "skills/open-project", "commands", ".zcode-plugin", "plugin.json"]:
                src = ROOT / rel
                if src.is_dir():
                    shutil.copytree(src, root / rel, ignore=shutil.ignore_patterns("__pycache__"))
                elif src.is_file():
                    (root / rel).parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, root / rel)
            (root / "skills/open-project/scripts/private.sqlite").write_bytes(b"not a package resource")
            with self.assertRaises(ValueError):
                builder.build(root, Path(td) / "package")

    def test_missing_runtime_module_cannot_be_packaged(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as td:
            root = Path(td) / "source"
            root.mkdir()
            for rel in ["LICENSE", "VERSION", "SOURCE.json", "skills/open-project", "commands", ".zcode-plugin", "plugin.json"]:
                original = ROOT / rel
                if original.is_dir():
                    shutil.copytree(original, root / rel, ignore=shutil.ignore_patterns("__pycache__"))
                elif original.is_file():
                    (root / rel).parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(original, root / rel)
            (root / "skills/open-project/scripts/plan_render.py").unlink()
            with self.assertRaisesRegex(ValueError, "Missing runtime resource"):
                builder.build(root, Path(td) / "package")

class EditionBoundaryTests(unittest.TestCase):
    def test_native_manifest_matches_edition(self):
        info = json.loads((ROOT / "SOURCE.json").read_text(encoding="utf-8"))
        skill = (ROOT / "skills/open-project/SKILL.md").read_text(encoding="utf-8")
        if info["edition"] == "zcode":
            self.assertTrue((ROOT / ".zcode-plugin/plugin.json").is_file())
            self.assertFalse((ROOT / "plugin.json").exists())
            self.assertFalse((ROOT / "skills/open-project/agents/openai.yaml").exists())
            self.assertIn("ReadSessionContext", skill)
            self.assertIn("subagent_type", skill)
            self.assertIn("model: <provider/model>", skill)
            agent = (ROOT / "skills/open-project/templates/agent.template.md").read_text(encoding="utf-8")
            self.assertTrue(agent.startswith("---\n"))
            self.assertIn("model: <PROVIDER/MODEL", agent)
            self.assertIn("唔准留空、唔准寫", agent)
        else:
            self.assertTrue((ROOT / "plugin.json").is_file())
            self.assertFalse((ROOT / ".zcode-plugin").exists())
            self.assertFalse((ROOT / "commands").exists())
            policy = (ROOT / "skills/open-project/agents/openai.yaml").read_text(encoding="utf-8")
            self.assertIn("allow_implicit_invocation: false", policy)
            self.assertNotIn('allow_implicit_invocation: "false"', policy)
            self.assertNotIn("ReadSessionContext", skill)
            self.assertNotIn("subagent_type", skill)

class CodexMetadataTests(unittest.TestCase):
    def test_codex_onboarding_reference_is_a_required_runtime_resource(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as td:
            root = Path(td) / "source"
            root.mkdir()
            for rel in ["LICENSE", "VERSION", "SOURCE.json", "skills/open-project", "plugin.json"]:
                original = ROOT / rel
                if original.is_dir():
                    shutil.copytree(original, root / rel, ignore=shutil.ignore_patterns("__pycache__"))
                elif original.is_file():
                    (root / rel).parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(original, root / rel)
            (root / "skills/open-project/references/gitnexus-onboarding.md").unlink()
            with self.assertRaisesRegex(ValueError, "Missing runtime resource.*gitnexus-onboarding"):
                builder.build(root, Path(td) / "package")

    def metadata(self, policy):
        return ('interface:\n  display_name: "Open Project"\n'
                '  short_description: "Explicit workflow"\n' + policy).encode("utf-8")

    def test_correct_manual_only_mapping_is_required(self):
        value = builder.validate_codex_metadata(self.metadata('policy:\n  allow_implicit_invocation: false\n'))
        self.assertIs(value["policy"]["allow_implicit_invocation"], False)

    def test_false_under_interface_does_not_mask_true_policy(self):
        raw = self.metadata('  allow_implicit_invocation: false\npolicy:\n  allow_implicit_invocation: true\n')
        with self.assertRaises(ValueError):
            builder.validate_codex_metadata(raw)

    def test_quoted_false_and_duplicate_policy_are_rejected(self):
        for policy in ['policy:\n  allow_implicit_invocation: "false"\n',
                       'policy:\n  allow_implicit_invocation: false\npolicy:\n  allow_implicit_invocation: true\n',
                       'policy:\n  allow_implicit_invocation: false\n  allow_implicit_invocation: true\n']:
            with self.subTest(policy=policy), self.assertRaises(ValueError):
                builder.validate_codex_metadata(self.metadata(policy))

if __name__ == "__main__":
    unittest.main()
