#!/usr/bin/env python3
"""Build an isolated local plugin from an explicit source allowlist. Never install."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SKILL = Path("skills/open-project")
ALLOWED = {"scripts": {".py"}, "templates": {".md", ".html", ".json", ".toml"}, "schemas": {".json"}, "references": {".md"}}

def is_link(item):
    try:
        return item.is_symlink() or bool(getattr(item.lstat(), "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))
    except FileNotFoundError:
        return False

def digest(raw):
    return hashlib.sha256(raw).hexdigest()

def validate_codex_metadata(raw):
    """Validate this package's declared two-level YAML subset, not arbitrary YAML."""
    sections = {}
    section = None
    for number, line in enumerate(raw.decode("utf-8").splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if "\t" in line:
            raise ValueError("Tabs are not supported in skill metadata")
        top = re.fullmatch(r"([a-z_]+):\s*(?:#.*)?", line)
        if top:
            section = top.group(1)
            if section not in {"interface", "policy"} or section in sections:
                raise ValueError("Unsupported or duplicate metadata mapping: " + section)
            sections[section] = {}
            continue
        item = re.fullmatch(r"  ([a-z_]+):\s*(.*?)\s*", line)
        if not item or section is None:
            raise ValueError("Unsupported metadata syntax at line " + str(number))
        key, value = item.groups()
        if key in sections[section]:
            raise ValueError("Duplicate metadata field: " + section + "." + key)
        if section == "policy":
            if key != "allow_implicit_invocation":
                raise ValueError("Unsupported policy field: " + key)
            if not re.fullmatch(r"false(?:\s+#.*)?", value):
                raise ValueError("policy.allow_implicit_invocation must be the YAML boolean false")
            sections[section][key] = False
        else:
            if key not in {"display_name", "short_description", "default_prompt", "icon_small", "icon_large", "brand_color"}:
                raise ValueError("Unsupported interface field: " + key)
            try:
                decoded = json.loads(value)
            except ValueError as exc:
                raise ValueError("Interface strings must use JSON-compatible YAML double quotes") from exc
            try:
                decoded.encode("utf-8") if isinstance(decoded, str) else None
            except UnicodeError as exc:
                raise ValueError("Interface fields require valid Unicode") from exc
            if not isinstance(decoded, str) or not decoded.strip():
                raise ValueError("Interface fields must be nonblank strings")
            sections[section][key] = decoded
    if sections.get("policy", {}).get("allow_implicit_invocation") is not False:
        raise ValueError("Explicit-only policy is required under the policy mapping")
    if not all(sections.get("interface", {}).get(key) for key in ("display_name", "short_description")):
        raise ValueError("Skill interface requires display_name and short_description")
    return sections

def source_files(root):
    info = json.loads((root / "SOURCE.json").read_text(encoding="utf-8"))
    edition = info["edition"]
    if edition not in ("zcode", "codex"):
        raise ValueError("Unknown source edition")
    selected = [Path("LICENSE"), Path("VERSION"), Path("SOURCE.json"), SKILL / "SKILL.md"]
    if edition == "zcode":
        selected += [Path(".zcode-plugin/plugin.json"), Path("commands/open-project.md")]
    else:
        selected += [Path("plugin.json"), SKILL / "agents/openai.yaml"]
        compat = Path(".codex-plugin/plugin.json")
        if (root / compat).is_file():
            selected.append(compat)
    for directory, extensions in ALLOWED.items():
        folder = root / SKILL / directory
        if folder.exists():
            for item in sorted(folder.iterdir()):
                if item.name == "__pycache__":
                    continue
                if is_link(item):
                    raise ValueError("Symlink/junction source rejected: " + str(item.relative_to(root)))
                if item.is_dir():
                    raise ValueError("Unexpected nested source directory: " + str(item.relative_to(root)))
                if item.suffix.lower() not in extensions:
                    raise ValueError("Unexpected source resource: " + str(item.relative_to(root)))
                selected.append(item.relative_to(root))
    data = {}
    for relative in selected:
        current = root
        for part in relative.parts:
            current = current / part
            if is_link(current):
                raise ValueError("Symlink/junction source rejected")
        if not current.is_file():
            raise ValueError("Missing package resource: " + str(relative))
        raw = current.read_bytes()
        if len(raw) > 2 * 1024 * 1024:
            raise ValueError("Oversized package resource: " + str(relative))
        raw.decode("utf-8")
        data[relative.as_posix()] = raw
    mandatory = {"SKILL.md",
        "scripts/plan_contract.py", "scripts/plan_render.py", "scripts/render-plan.py",
        "scripts/gate-check.py", "scripts/promote.py", "scripts/discover-sessions.py",
        "schemas/plan.schema.json", "references/workflow-contract.md",
        "references/host-" + edition + ".md",
        "templates/PLAN.template.md", "templates/plan-report.template.html",
        "templates/product_specification.template.md", "templates/agent.template.md",
        "templates/memory.template.md", "templates/project_status.template.md",
        "templates/FROZEN.template.md", "templates/REVIEW_REPORT.template.md",
        "templates/plugin.template.json", "templates/marketplace.template.json"}
    if edition == "codex":
        mandatory.add("templates/agent.template.toml")
    missing = sorted(str(SKILL / relative).replace("\\", "/") for relative in mandatory
                     if (SKILL / relative).as_posix() not in data)
    if missing:
        raise ValueError("Missing runtime resource: " + ", ".join(missing))
    manifest_path = ".zcode-plugin/plugin.json" if edition == "zcode" else "plugin.json"
    manifest = json.loads(data[manifest_path])
    if (root / "VERSION").read_text(encoding="utf-8").strip() != info["skill_version"]:
        raise ValueError("Skill version and SOURCE.json disagree")
    if manifest["version"] != info["plugin_version"]:
        raise ValueError("Plugin version and SOURCE.json disagree")
    if edition == "codex":
        if manifest.get("$schema") != "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json":
            raise ValueError("Portable manifest schema missing")
        validate_codex_metadata(data[(SKILL / "agents/openai.yaml").as_posix()])
    elif manifest.get("skills") != "skills" or manifest.get("commands") != "commands":
        raise ValueError("ZCode manifest paths must retain native conventions")
    return info, data

def build(root, output, source_ref="WORKTREE"):
    root = Path(root).resolve()
    output = Path(output).absolute()
    if source_ref != "WORKTREE" and not re.fullmatch(r"[0-9a-f]{40}", source_ref):
        raise ValueError("source-ref must be a full Git commit SHA or WORKTREE")
    current = Path(output.anchor)
    for part in output.parts[1:]:
        current /= part
        if is_link(current):
            raise ValueError("Symlink/junction output rejected")
    if output == root or output.is_relative_to(root / "skills") or root.is_relative_to(output):
        raise ValueError("Output cannot replace source or contain source")
    info, data = source_files(root)
    records = [{"path": p, "sha256": digest(b), "bytes": len(b)} for p, b in sorted(data.items())]
    tree_hash = digest(json.dumps(records, sort_keys=True, separators=(",", ":")).encode())
    package = {"schema_version": "1.0", "edition": info["edition"], "skill_version": info["skill_version"], "plugin_version": info["plugin_version"], "source_ref": source_ref, "source_tree_sha256": tree_hash, "files": records, "status": "PACKAGED", "installation_verified": False, "invocation_verified": False}
    data["PACKAGE-MANIFEST.json"] = (json.dumps(package, ensure_ascii=False, indent=2) + "\n").encode()
    if output.exists():
        existing = {}
        for item in output.rglob("*"):
            if is_link(item):
                raise ValueError("Existing package contains symlink/junction")
            if item.is_file():
                existing[item.relative_to(output).as_posix()] = item.read_bytes()
        if existing == data:
            return {**package, "build": "NO_OP", "output": str(output)}
        raise ValueError("Output exists with different bytes; choose a new output directory")
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".open-project-build-", dir=output.parent))
    try:
        for relative, raw in data.items():
            target = staging / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
        os.rename(staging, output)
    finally:
        if staging.exists():
            if is_link(staging) or staging.resolve().parent != output.parent.resolve() or not staging.name.startswith(".open-project-build-"):
                raise ValueError("Unsafe temporary cleanup target")
            shutil.rmtree(staging)
    return {**package, "build": "BUILT", "output": str(output)}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--source-ref", default="WORKTREE", help="Verified source commit, or WORKTREE before publication")
    args = parser.parse_args()
    try:
        info = json.loads((ROOT / "SOURCE.json").read_text(encoding="utf-8"))
        name = "open-project-codex" if info["edition"] == "codex" else "open-project"
        output = args.output or ROOT / "build" / info["edition"] / name
        print(json.dumps(build(ROOT, output, args.source_ref), ensure_ascii=False, indent=2))
        return 0
    except (ValueError, OSError, KeyError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "ERROR", "error": str(exc)}, ensure_ascii=False))
        return 1
if __name__ == "__main__":
    sys.exit(main())
