"""Preview/apply a user-authorized, explicit-open-project-only instruction exception."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import tempfile

BEGIN = b'<!-- open-project-jev-bypass:v1:begin -->'
END = b'<!-- open-project-jev-bypass:v1:end -->'
BLOCK = b'\n\n' + BEGIN + b'''
## Explicit open-project: standing Jev routing exception

User-authorized policy: when the user explicitly invokes open-project (including
the selected plugin/Skill or /open-project), automatically bypass TypeSafe/Jev
task routing, feasibility, scoring, monitoring and completion arbitration for
that open-project task and its scoped children. Do not call Jev as a prerequisite,
wait for its route, or ask again for a Jev bypass. The parent coordinates available
native tools/agents directly and retains independent review and actual evidence.
Record USER_AUTHORIZED_BYPASS with this policy and the current invocation as refs;
do not claim Jev PASS, fabricate receipts, or rewrite earlier blocked records.

This is a narrow exception to generic user-level Jev orchestration requirements,
including "No silent parent bypass". It is disclosed standing authorization,
not a global disable. Mere mention, quoted/reviewed Skill text, installation, an
unrelated task, or completion/cancellation of the invoked task does not activate
or extend it. A later explicit user instruction to use Jev overrides the exception.
Carry the same bounded exception to any authorized child; never rebind projects.

Continue all authorized independent work, including inventory, relevant history
deep-reading, five full drafts, rendering, gates and independent review. A Jev
abstention, outage, missing route/tool or old BLOCKED_ROUTING is not a stop reason
for work covered by this exception. A checkpoint marked PARTIAL is not completion.
If a real non-Jev dependency stops one step, record it and continue other work.

Preserve system/developer/platform rules, sandbox and OS permissions, explicit
user limits, exact write/deploy/publish approvals, drift checks and acceptance
gates. Do not disable or evade host security hooks. Preserve model/provider
settings, native agent policies, GUI/browser rules and JevCompact. Codex retains
GitNexus obligations; ZCode keeps GitNexus N/A. Do not edit unrelated global rules.
''' + END + b'\n'


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def is_link(path):
    try:
        return path.is_symlink() or bool(getattr(path.lstat(), 'st_file_attributes', 0) &
                                        getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0x400))
    except FileNotFoundError:
        return False


def read_target(path):
    path = Path(path).absolute()
    if path.name not in {'AGENTS.md', 'AGENTS.override.md'}:
        raise ValueError('Target must be the selected host AGENTS.md or AGENTS.override.md')
    for p in [path, *path.parents]:
        if is_link(p):
            raise ValueError('Symlink/junction target or ancestor is unsupported')
    if path.exists() and (not path.is_file() or path.stat().st_nlink != 1):
        raise ValueError('Target must be an ordinary single-link file')
    if not path.parent.is_dir():
        raise ValueError('Host instructions parent must already exist')
    raw = path.read_bytes() if path.exists() else None
    if raw is not None:
        raw.decode('utf-8-sig')
    return path, raw


def proposed(raw, remove=False):
    old = raw or b''
    if BEGIN in old or END in old:
        if old.count(BEGIN) != 1 or old.count(END) != 1 or old.count(BLOCK) != 1:
            raise ValueError('Managed policy changed/ambiguous; preserve and inspect it')
        return old.replace(BLOCK, b'', 1) if remove else old
    return old if remove else old + BLOCK


def configure(path, *, apply=False, expected=None, remove=False):
    path, raw = read_target(path)
    before = digest(raw) if raw is not None else 'NOT_EXISTS'
    after = proposed(raw, remove)
    result = {'target': str(path), 'before_sha256': before,
              'after_sha256': digest(after), 'policy': 'open-project-jev-bypass/v1',
              'action': 'REMOVE' if remove else 'ENABLE', 'behavior_verified': False,
              'active': BLOCK in (raw or b''), 'status': 'PREVIEW', 'backup': None}
    if not apply:
        return result
    if expected != before:
        raise ValueError('Expected baseline mismatch; preview again and inspect drift')
    if after == (raw or b''):
        return {**result, 'status': 'NO_OP'}
    if raw is not None:
        backup = path.with_name(path.name + '.open-project-jev-backup-' + before + '.bak')
        if backup.exists():
            if is_link(backup) or backup.stat().st_nlink != 1 or backup.read_bytes() != raw:
                raise ValueError('Backup conflicts; no overwrite')
        else:
            with backup.open('xb') as out:
                out.write(raw)
        result['backup'] = str(backup)
    # Cooperative pre-write drift check; not an OS lock against other writers.
    if read_target(path)[1] != raw:
        raise ValueError('Source drifted before write; backup retained')
    fd, name = tempfile.mkstemp(prefix='.open-project-jev-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as out:
            out.write(after)
            out.flush()
            os.fsync(out.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)
    if path.read_bytes() != after:
        raise ValueError('Post-write bytes mismatch; inspect target and backup')
    return {**result, 'status': 'APPLIED', 'active': not remove}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--instructions', required=True, type=Path)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--expected-sha256')
    parser.add_argument('--remove', action='store_true')
    args = parser.parse_args()
    try:
        result = configure(args.instructions, apply=args.apply,
                           expected=args.expected_sha256, remove=args.remove)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (ValueError, OSError, UnicodeError) as exc:
        print(json.dumps({'status': 'BLOCKED', 'error': str(exc)}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
