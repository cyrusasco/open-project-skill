"""Read-only verification of native state, installed bytes and effective policy.

Native plugin-list JSON arrives on stdin from the host CLI, never a fabricated
success flag. This does not run a model turn or prove invocation behavior.
"""
from pathlib import Path
import argparse
import json
import runpy
import sys

sys.dont_write_bytecode = True


def verify(source, host, native):
    source, host = Path(source).resolve(), Path(host).resolve()
    builder = runpy.run_path(str(source / 'scripts/build-plugin.py'))
    info, resources = builder['source_files'](source)
    if info['edition'] != 'codex':
        raise ValueError('Expected Codex edition')
    name = 'open-project-codex'
    rows = [r for r in native.get('installed', []) if r.get('pluginId') == name + '@' + name]
    errors = []
    expected = info['plugin_version']
    native_ok = len(rows) == 1
    if native_ok:
        p = rows[0]
        native_path = p.get('source', {}).get('path')
        native_ok = (p.get('installed') is True and p.get('enabled') is True
                     and p.get('version') == expected and p.get('name') == name
                     and p.get('marketplaceName') == name
                     and p.get('source', {}).get('source') == 'local'
                     and isinstance(native_path, str) and bool(native_path.strip())
                     and Path(native_path).is_absolute() and Path(native_path).resolve() == source)
    if not native_ok:
        errors.append('Native plugin identity/version/enabled/source does not match.')
    cache = host / 'plugins/cache' / name / name / expected
    expected_runtime = {rel for rel in resources if rel.startswith('skills/')}
    actual_runtime = set()
    unexpected = []
    if cache.is_dir():
        if builder['is_link'](cache) or builder['is_link'](cache/'skills'):
            raise ValueError('Installed runtime root is a link/reparse point')
        for item in (cache/'skills').rglob('*'):
            rel = item.relative_to(cache).as_posix()
            if builder['is_link'](item):
                unexpected.append(rel)
            elif item.is_file() and '__pycache__' not in item.parts:
                actual_runtime.add(rel)
    unexpected += sorted(actual_runtime - expected_runtime)
    mismatched = [rel for rel, raw in resources.items()
                  if not (cache / rel).is_file() or (cache / rel).read_bytes() != raw]
    if mismatched:
        errors.append('Installed resource bytes missing or different from source.')
    if unexpected:
        errors.append('Unexpected installed runtime resources or links.')
    override = host / 'AGENTS.override.md'
    instructions = override if override.is_file() and override.read_text(encoding='utf-8-sig').strip() else host / 'AGENTS.md'
    helper = runpy.run_path(str(source / 'scripts/configure-jev-bypass.py'))
    policy = helper['configure'](instructions)
    if not policy['active']:
        errors.append('Effective user instructions lack the scoped Jev exception; a restart cannot add it.')
    return {'status': 'SOURCE_AND_POLICY_VERIFIED' if not errors else 'INSTALLATION_INCOMPLETE',
            'version': expected, 'native_verified': native_ok,
            'installed_bytes_verified': not mismatched and not unexpected,
            'mismatched_resources': mismatched, 'unexpected_resources': unexpected,
            'jev_policy_verified': policy['active'], 'effective_instructions': str(instructions),
            'instructions_sha256': policy['before_sha256'], 'allow_implicit_invocation': False,
            'invocation_behavior_verified': False, 'errors': errors,
            'limits': 'Read-only observation; no model turn, host security bypass or GitNexus execution.'}


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--host-root', type=Path, required=True)
    args = parser.parse_args()
    try:
        result = verify(args.source_root, args.host_root, json.load(sys.stdin))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        result = {'status': 'INSTALLATION_INCOMPLETE', 'errors': [str(exc)],
                  'invocation_behavior_verified': False}
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result['status'] == 'SOURCE_AND_POLICY_VERIFIED' else 1


if __name__ == '__main__':
    raise SystemExit(main())
