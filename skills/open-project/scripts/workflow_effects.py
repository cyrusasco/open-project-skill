"""Validate declared file effects and captured Git observations; perform no effects.

Receipts bind content and scope, not human authorization or OS permission. This
module never moves files, invokes Git, changes cwd, or edits repository state.
"""
from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path

from plan_contract import PacketError, _hash, _relative, packet_digest, resolve_inside, sha256

MAX_RECEIPT_BYTES = 64 * 1024
MAX_GIT_STDOUT_BYTES = 1024 * 1024
GIT_COMMAND = ['git', 'status', '--porcelain=v1', '--untracked-files=all', '--ignored']
TEXT = {'type': 'string', 'minLength': 1, 'pattern': r'\S'}
STRING = {'type': 'string'}
DIGEST = {'type': 'string', 'pattern': '^[a-f0-9]{64}$'}


def _object(properties, optional=()):
    return {'type': 'object', 'properties': properties,
            'required': [key for key in properties if key not in optional],
            'additionalProperties': False}


def effects_schema():
    reference = _object({'root_id': TEXT, 'path': TEXT, 'sha256': DIGEST})
    optional_reference = _object({'root_id': STRING, 'path': STRING, 'sha256': STRING})
    counts = _object({key: {'type': 'integer', 'minimum': 0}
                      for key in ('tracked', 'untracked', 'ignored')})
    git = _object({
        'status': {'enum': ['NOT_APPLICABLE', 'PLANNED', 'OBSERVED']}, 'reason': TEXT,
        'root_id': TEXT, 'root_path': TEXT, 'observed_at': TEXT, 'exit_code': {'type': 'integer', 'minimum': 0},
        'command': {'type': 'array', 'items': TEXT}, 'stdout': reference,
        'claimed_clean': {'type': 'boolean'}, 'counts': counts,
    }, optional=('root_id', 'root_path', 'observed_at', 'exit_code', 'command', 'stdout', 'claimed_clean', 'counts'))
    action = _object({
        'id': TEXT, 'kind': {'enum': ['copy', 'move', 'archive']},
        'source': reference,
        'destination': _object({'root_id': TEXT, 'path': TEXT, 'baseline_sha256': TEXT}),
        'expected_sha256': DIGEST, 'source_after': {'enum': ['PRESENT', 'ABSENT']},
        'superseded_by': optional_reference,
        'state': {'enum': ['PLANNED', 'COMPLETE', 'BLOCKED']},
        'reason': TEXT, 'receipt': optional_reference,
    })
    return _object({'actions': {'type': 'array', 'items': action}, 'git': git})


def _timestamp(value):
    try:
        result = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if result.tzinfo is None:
            raise ValueError()
    except (AttributeError, TypeError, ValueError):
        raise PacketError('effect observation requires timezone-qualified ISO timestamp') from None


def _roots(plan):
    roots = plan['workflow']['roots']
    return {'docs': roots['docs_root'], **{row['id']: row['path'] for row in roots['source_roots']}}


def _location(plan, reference):
    """Raw resolver, deliberately without archived-source fallback/recursion."""
    roots = _roots(plan)
    identity = reference.get('root_id', 'docs')
    if identity not in roots:
        raise PacketError('effect references unknown root_id')
    return resolve_inside(roots[identity], reference['path'])


def _reference(value, roots, optional=False):
    if optional and not any(value.values()):
        return False
    if not all(isinstance(value[key], str) and value[key] for key in ('root_id', 'path', 'sha256')):
        raise PacketError('effect reference must be completely populated or completely empty')
    if value['root_id'] not in roots:
        raise PacketError('effect references unknown root_id: ' + value['root_id'])
    _relative(value['path'], 'effect reference path')
    _hash(value['sha256'], 'effect reference sha256')
    return True


def _control_path(path):
    return path.split('/')[0].casefold() in ('.git', '.open-project-promotion') or path.casefold() in (
        'md-drafts/plan-data.json', 'md-drafts/plan.draft.md', 'md-drafts/plan-report.draft.html')


def validate_effects_structure(plan):
    """Require typed effects even when no filesystem/Git operation is adopted."""
    from workflow_contract import _shape
    effects = plan['workflow'].get('effects')
    _shape(effects, effects_schema(), 'workflow.effects')
    roots = _roots(plan)
    actions = effects['actions']
    ids = [row['id'] for row in actions]
    if len(ids) != len(set(ids)):
        raise PacketError('duplicate effect action id')
    destinations = set()
    decisions = {row['action_id']: row['state'] for row in plan['workflow']['decisions']['current']}
    for action in actions:
        _reference(action['source'], roots)
        destination = action['destination']
        if destination['root_id'] not in roots:
            raise PacketError('effect destination has unknown root_id')
        _relative(destination['path'], 'effect destination path')
        _hash(destination['baseline_sha256'], 'effect destination baseline', baseline=True)
        if _control_path(destination['path']) or _control_path(action['source']['path']):
            raise PacketError('effect cannot mutate packet or repository control paths')
        target = (destination['root_id'], destination['path'].casefold())
        origin = (action['source']['root_id'], action['source']['path'].casefold())
        if target == origin or target in destinations:
            raise PacketError('effect source/destination collision or duplicate target')
        destinations.add(target)
        if action['expected_sha256'] != action['source']['sha256']:
            raise PacketError('file copy/move/archive must preserve original bytes')
        if ((action['kind'] == 'copy' and action['source_after'] != 'PRESENT') or
                (action['kind'] == 'move' and action['source_after'] != 'ABSENT')):
            raise PacketError('copy/move source_after contradicts operation')
        supersedes = _reference(action['superseded_by'], roots, optional=True)
        if action['kind'] == 'archive' and not supersedes:
            raise PacketError('archive requires explicit superseded_by mapping')
        if supersedes:
            superseding = (action['superseded_by']['root_id'], action['superseded_by']['path'].casefold())
            if superseding in (target, origin):
                raise PacketError('superseded_by must identify the distinct replacement file')
        receipt = _reference(action['receipt'], roots, optional=True)
        if action['state'] == 'COMPLETE' and not receipt:
            raise PacketError('completed effect requires actual action receipt')
        state = decisions.get(action['id'])
        if state is None or (action['state'] == 'COMPLETE' and state != 'COMPLETED'):
            raise PacketError('effect action must map to its current decision state')
        if action['state'] != 'COMPLETE' and state == 'COMPLETED':
            raise PacketError('effect and decision completion states contradict')
    changes = plan['folder_changes']
    if any(not isinstance(row, dict) or not isinstance(row.get('id'), str)
           or not row['id'].strip() or set(row) - {'id', 'description'}
           or ('description' in row and not isinstance(row['description'], str))
           for row in changes):
        raise PacketError('folder_changes requires typed action id and optional description')
    change_ids = [row['id'] for row in changes]
    if len(change_ids) != len(set(change_ids)) or set(change_ids) != set(ids):
        raise PacketError('folder_changes IDs must map exactly to declared effect actions')
    git = effects['git']
    if git['status'] == 'NOT_APPLICABLE':
        if set(git) != {'status', 'reason'}:
            raise PacketError('N/A git observation cannot contain observed/clean claims')
    elif git['status'] == 'PLANNED':
        if set(git) != {'status', 'reason', 'root_id'} or git['root_id'] not in roots:
            raise PacketError('planned git observation requires only declared root_id and reason')
    else:
        expected = {'status', 'reason', 'root_id', 'root_path', 'observed_at', 'exit_code', 'command',
                    'stdout', 'claimed_clean', 'counts'}
        if set(git) != expected or git['root_id'] not in roots:
            raise PacketError('observed git result is incomplete or has unknown root')
        if git['command'] != GIT_COMMAND or git['exit_code'] != 0:
            raise PacketError('git observation requires successful bounded porcelain command')
        if git['root_path'] != roots[git['root_id']]:
            raise PacketError('git observation root_path differs from current declared root')
        _timestamp(git['observed_at'])
        _reference(git['stdout'], roots)


def effect_identity(plan, action):
    """Bind immutable action scope and concrete roots, without a self-receipt hash.

    A later packet revision can retain an unchanged effect receipt. Changes to
    the action or its used roots change this identity and invalidate old evidence.
    """
    fields = ('id', 'kind', 'source', 'destination', 'expected_sha256', 'source_after', 'superseded_by')
    identity = {key: action[key] for key in fields}
    used = {action['source']['root_id'], action['destination']['root_id']}
    if action['superseded_by']['root_id']:
        used.add(action['superseded_by']['root_id'])
    roots = _roots(plan)
    return packet_digest({'plan_id': plan['plan_id'], 'action': identity,
                          'root_bindings': {key: roots[key] for key in sorted(used)}})


def _read_reference(plan, project, reference, maximum=None):
    location = _location(plan, reference)
    if maximum is None:
        raw = location.read_bytes()
    else:
        with location.open('rb') as stream:
            raw = stream.read(maximum + 1)
        if len(raw) > maximum:
            raise PacketError('effect receipt/observation exceeds bounded capture size')
    if sha256(raw) != reference['sha256']:
        raise PacketError('effect reference hash mismatch: ' + reference['path'])
    return location, raw


def _json(raw):
    from plan_contract import _pairs, _constant
    try:
        return json.loads(raw.decode('utf-8'), object_pairs_hook=_pairs, parse_constant=_constant)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise PacketError('effect receipt must be valid UTF-8 JSON') from exc


def _action_receipt(plan, project, action):
    from workflow_contract import _shape
    _, raw = _read_reference(plan, project, action['receipt'], MAX_RECEIPT_BYTES)
    result = _json(raw)
    _shape(result, _object({
        'schema_version': {'enum': ['open-project/effect-receipt/1.0']},
        'plan_id': TEXT, 'executed_revision': TEXT, 'action_id': TEXT,
        'action_sha256': DIGEST, 'observed_at': TEXT, 'result': {'enum': ['COMPLETE']},
        'source_before_sha256': DIGEST, 'destination_before_sha256': TEXT,
        'destination_after_sha256': DIGEST, 'source_after': {'enum': ['PRESENT', 'ABSENT']},
        'superseded_by': _object({'root_id': STRING, 'path': STRING, 'sha256': STRING}),
    }), 'effect receipt')
    _timestamp(result['observed_at'])
    if (result['plan_id'] != plan['plan_id'] or result['action_id'] != action['id']
            or result['action_sha256'] != effect_identity(plan, action)
            or result['source_before_sha256'] != action['source']['sha256']
            or result['destination_before_sha256'] != action['destination']['baseline_sha256']
            or result['destination_after_sha256'] != action['expected_sha256']
            or result['source_after'] != action['source_after']
            or result['superseded_by'] != action['superseded_by']):
        raise PacketError('action receipt does not bind declared source/destination/supersedes scope')
    origin = _location(plan, action['source'])
    destination = _location(plan, action['destination'])
    if origin == destination:
        raise PacketError('source and destination resolve to same location')
    if sha256(destination.read_bytes()) != action['expected_sha256']:
        raise PacketError('completed effect destination bytes mismatch')
    if action['source_after'] == 'ABSENT':
        if origin.exists():
            raise PacketError('completed move/archive source still exists')
    elif sha256(origin.read_bytes()) != action['source']['sha256']:
        raise PacketError('retained effect source bytes changed')
    if action['superseded_by']['root_id']:
        _read_reference(plan, project, action['superseded_by'])


def preserved_source_location(plan, project, source):
    """Resolve a removed source only through its validated exact preservation map.

    Original source identity and hash stay unchanged. No content/path search or
    automatic rehash can turn an arbitrary backup into a trusted source.
    """
    effects = plan.get('workflow', {}).get('effects')
    if not effects:
        return None
    root_id = source.get('root_id', 'docs')
    matches = [action for action in effects.get('actions', [])
               if action.get('kind') in ('move', 'archive') and action.get('state') == 'COMPLETE'
               and action.get('source_after') == 'ABSENT'
               and action.get('source', {}).get('root_id') == root_id
               and action.get('source', {}).get('path') == source.get('path')
               and action.get('source', {}).get('sha256') == source.get('sha256')]
    if not matches:
        return None
    validate_effects_structure(plan)
    if len(matches) != 1:
        raise PacketError('ambiguous archived source preservation mapping')
    action = matches[0]
    _action_receipt(plan, project, action)
    destination = _location(plan, action['destination'])
    if sha256(destination.read_bytes()) != source['sha256']:
        raise PacketError('preserved source bytes differ from original source identity')
    return destination


def porcelain_counts(raw):
    """Parse quoted-path-compatible porcelain v1 lines without retaining paths."""
    try:
        text = raw.decode('utf-8')
    except UnicodeError as exc:
        raise PacketError('git porcelain capture must be UTF-8') from exc
    counts = {'tracked': 0, 'untracked': 0, 'ignored': 0}
    if not raw:
        return counts
    for line in text.splitlines():
        if len(line) < 4 or line[2] != ' ' or not line[3:].strip():
            raise PacketError('malformed git porcelain line')
        status = line[:2]
        if status == '??':
            counts['untracked'] += 1
        elif status == '!!':
            counts['ignored'] += 1
        elif (status != '  ' and all(char in ' MADRCUT' for char in status)):
            counts['tracked'] += 1
        else:
            raise PacketError('unsupported git porcelain status')
    return counts


def effects_findings(plan, project, stage='plan'):
    """Return errors for missing/inconsistent effects; never grant or execute them."""
    if stage not in ('plan', 'completion'):
        raise PacketError('effects stage must be plan or completion')
    findings = []
    def fail(code, message):
        findings.append({'severity': 'error', 'code': code, 'message': message})
    try:
        validate_effects_structure(plan)
    except (PacketError, KeyError, TypeError, ValueError) as exc:
        fail('W_EFFECT_STRUCTURE', str(exc))
        return findings
    effects = plan['workflow']['effects']
    for action in effects['actions']:
        try:
            if action['state'] == 'COMPLETE':
                _action_receipt(plan, project, action)
            elif stage == 'completion':
                raise PacketError('required effect action is not complete: ' + action['id'])
            elif action['state'] == 'PLANNED':
                origin, _ = _read_reference(plan, project, action['source'])
                destination = _location(plan, action['destination'])
                if origin == destination:
                    raise PacketError('source and destination resolve to same location')
                baseline = action['destination']['baseline_sha256']
                if baseline == 'NOT_EXISTS':
                    if destination.exists():
                        raise PacketError('effect destination baseline expected NOT_EXISTS')
                elif sha256(destination.read_bytes()) != baseline:
                    raise PacketError('effect destination baseline drifted')
        except (PacketError, OSError, UnicodeError) as exc:
            fail('W_EFFECT_ACTION', str(exc))
    git = effects['git']
    try:
        if git['status'] == 'NOT_APPLICABLE':
            if any(resolve_inside(root, '.git').exists() for root in _roots(plan).values()):
                raise PacketError('declared root has Git metadata; observation cannot be N/A')
        elif git['status'] == 'PLANNED':
            if stage == 'completion':
                raise PacketError('required git observation has not run')
        else:
            if not resolve_inside(_roots(plan)[git['root_id']], '.git').exists():
                raise PacketError('observed git root has no Git metadata')
            _, raw = _read_reference(plan, project, git['stdout'], MAX_GIT_STDOUT_BYTES)
            counts = porcelain_counts(raw)
            if counts != git['counts']:
                raise PacketError('git tracked/untracked/ignored counts contradict captured stdout')
            if git['claimed_clean'] is not (raw == b''):
                raise PacketError('git clean claim contradicts captured porcelain stdout')
    except (PacketError, OSError, UnicodeError) as exc:
        fail('W_EFFECT_GIT', str(exc))
    return findings
