"""Read-only relevance and continuation checks; never grants completion/approval."""
from pathlib import Path
import json

from plan_contract import PacketError, load_plan, packet_digest, resolve_inside, sha256, _pairs, _constant
from workflow_contract import _shape, source_location

TEXT = {'type': 'string', 'minLength': 1, 'pattern': r'\S'}
STRINGS = {'type': 'array', 'items': TEXT}


def obj(properties):
    return {'type': 'object', 'properties': properties, 'required': list(properties),
            'additionalProperties': False}


def array(item):
    return {'type': 'array', 'items': item}


def enum(*values):
    return {'enum': list(values)}


def checkpoint_schema():
    return obj({
        'schema_version': enum('open-project/followup/1.0'),
        'plan_id': TEXT, 'revision': TEXT,
        'packet_sha256': {'type': 'string', 'pattern': '^[a-f0-9]{64}$'},
        'scope': TEXT, 'inventory_evidence': STRINGS,
        'inventory': array(obj({'id': TEXT, 'source': TEXT, 'session_id': TEXT})),
        'screening': array(obj({
            'id': TEXT, 'relevance': enum('RELATED', 'UNRELATED', 'UNDETERMINED'),
            'basis': enum('scoped_search', 'bounded_context', 'verified_link', 'user_scope', 'metadata_only'),
            'reason': TEXT, 'evidence': STRINGS,
            'read': enum('FULL', 'PARTIAL', 'UNREAD', 'NOT_REQUIRED'), 'read_scope': TEXT,
        })),
        'tasks': array(obj({
            'id': TEXT, 'kind': enum('relevance', 'reading', 'attachment', 'other'),
            'session_ids': STRINGS, 'action': TEXT,
            'state': enum('READY', 'BLOCKED', 'DEFERRED', 'DONE'),
            'reason': TEXT, 'owner': TEXT, 'evidence': STRINGS,
            'authority_ref': {'type': 'string'},
            'blocker': enum('none', 'missing_source', 'permission', 'tool_limit', 'external_dependency'),
        })),
    })


def _unique(rows, label):
    ids = [r['id'] for r in rows]
    if len(ids) != len(set(ids)):
        raise PacketError('duplicate ' + label + ' identity')
    return set(ids)


def evaluate_checkpoint(plan, project, data):
    _shape(data, checkpoint_schema(), 'followup checkpoint')
    if Path(plan['workflow']['roots']['docs_root']).resolve() != Path(project).resolve():
        raise PacketError('checkpoint project root differs from canonical docs_root')
    if (data['plan_id'], data['revision'], data['packet_sha256']) != (
            plan['plan_id'], plan['revision'], packet_digest(plan)):
        raise PacketError('checkpoint belongs to another packet/revision')
    sources = {s['id']: s for s in plan['sources']}
    checked = set()
    def evidence(refs):
        if not refs:
            raise PacketError('checkpoint decision needs captured evidence')
        for ref in refs:
            if not ref.startswith('source:') or ref[7:] not in sources:
                raise PacketError('unknown checkpoint evidence reference: ' + ref)
            s = sources[ref[7:]]
            if s['id'] in checked:
                continue
            if s.get('kind') != 'file' or sha256(source_location(plan, project, s).read_bytes()) != s.get('sha256'):
                raise PacketError('checkpoint evidence must bind current captured file bytes: ' + ref)
            checked.add(s['id'])
    evidence(data['inventory_evidence'])
    inventory = _unique(data['inventory'], 'inventory')
    identities = [(r['source'], r['session_id']) for r in data['inventory']]
    if len(identities) != len(set(identities)):
        raise PacketError('duplicate source/session identity; record explicit aliases in evidence')
    screened = _unique(data['screening'], 'screening')
    if inventory != screened:
        raise PacketError('inventory/screening identity mismatch; missing screening is not unread history')
    _unique(data['tasks'], 'task')
    tasks = data['tasks']
    for task in tasks:
        if not set(task['session_ids']) <= inventory:
            raise PacketError('task references unknown inventory identity')
        evidence(task['evidence'])
        if task['state'] == 'BLOCKED':
            if task['blocker'] == 'none':
                raise PacketError('BLOCKED requires a concrete dependency, not PARTIAL or Jev routing')
        elif task['blocker'] != 'none':
            raise PacketError('only BLOCKED tasks may declare a blocker')
        if task['state'] == 'DEFERRED':
            if not task['authority_ref']:
                raise PacketError('DEFERRED requires the user scope/deferral evidence')
            evidence([task['authority_ref']])
    for row in data['screening']:
        evidence(row['evidence'])
        if row['relevance'] == 'UNRELATED' and row['basis'] not in ('scoped_search', 'bounded_context', 'user_scope'):
            raise PacketError('title/path/parent metadata alone cannot prove unrelatedness')
        if row['relevance'] == 'UNDETERMINED':
            kind = 'relevance'
        elif row['relevance'] == 'RELATED' and row['read'] != 'FULL':
            kind = 'reading'
        else:
            continue
        if not any(t['kind'] == kind and row['id'] in t['session_ids'] and t['state'] != 'DONE' for t in tasks):
            raise PacketError('unresolved relevance/related reading needs a continuation task: ' + row['id'])
    ready = [t['id'] for t in tasks if t['state'] == 'READY']
    pending = [t['id'] for t in tasks if t['state'] in ('BLOCKED', 'DEFERRED')]
    return {'status': 'CONTINUE_REQUIRED' if ready else 'CHECKPOINT_JUSTIFIED',
            'can_stop': not ready, 'complete': False,
            'plan_id': plan['plan_id'], 'revision': plan['revision'],
            'packet_sha256': packet_digest(plan), 'ready_tasks': ready,
            'pending_tasks': pending,
            'screening_counts': {k: sum(r['relevance'] == k for r in data['screening'])
                                 for k in ('RELATED', 'UNRELATED', 'UNDETERMINED')},
            'errors': [], 'warnings': [],
            'limits': 'Validates declared screening/continuation and evidence bytes, not relevance truth, '
                      'inventory exhaustiveness, user authentication, workflow completion or host enforcement.'}


def inspect_checkpoint(project):
    try:
        plan = load_plan(project)
        path = resolve_inside(project, 'md-drafts/followup-checkpoint.json')
        with path.open('rb') as stream:
            raw = stream.read(2 * 1024 * 1024 + 1)
        if len(raw) > 2 * 1024 * 1024:
            raise PacketError('checkpoint exceeds bounded metadata size')
        data = json.loads(raw.decode('utf-8'), object_pairs_hook=_pairs, parse_constant=_constant)
        return evaluate_checkpoint(plan, Path(project), data)
    except (PacketError, OSError, UnicodeError, ValueError, KeyError, TypeError) as exc:
        return {'status': 'CHECKPOINT_INCOMPLETE', 'can_stop': False, 'complete': False,
                'errors': [str(exc)], 'warnings': []}
