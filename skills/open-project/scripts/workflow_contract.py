"""Packet 2.0 workflow obligations; mechanical evidence checks, not host enforcement.

The small schema evaluator below implements only the vocabulary emitted here.
Human approval, source interpretation and reviewer independence still require
independent inspection; a hash or a boolean is not their proof.
"""
from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import re

from plan_contract import PacketError, _hash, _relative, expected_content, packet_digest, read_draft, resolve_inside, sha256

ROLE_SECTIONS = {
    'project_manual': ('purpose', 'roots', 'reading_order', 'authority', 'tools', 'sop', 'verification', 'handover'),
    'specification': ('goals', 'features', 'settings', 'scope', 'acceptance', 'sources'),
    'project_status': ('snapshot', 'results', 'unknowns', 'next_steps'),
    'memory': ('events', 'decisions', 'sources'),
    'independent_review': ('scope', 'reviewer', 'checks', 'outcome'),
}
REVIEW_AREAS = ('frozen', 'parity', 'structure', 'paths', 'secrets', 'verification',
                'git', 'native_agents', 'logic', 'claims', 'plan_views', 'promotion')
TEXT = {'type': 'string', 'minLength': 1, 'pattern': r'\S'}
STRING = {'type': 'string'}
BOOLEAN = {'type': 'boolean'}
INTEGER = {'type': 'integer', 'minimum': 0}
DIGEST = {'type': 'string', 'pattern': '^[a-f0-9]{64}$'}


def array(item, minimum=0):
    return {'type': 'array', 'items': item, 'minItems': minimum}


def enum(*values):
    return {'enum': list(values)}


def obj(properties, optional=()):
    return {'type': 'object', 'properties': properties,
            'required': [key for key in properties if key not in optional],
            'additionalProperties': False}


def workflow_schema():
    strings = array(TEXT)
    ref = obj({'root_id': TEXT, 'path': TEXT, 'sha256': DIGEST})
    properties = {
        'roots': obj({
            'destination_mode': enum('new_folder', 'existing_project'), 'docs_root': TEXT,
            'source_roots': array(obj({'id': TEXT, 'path': TEXT})),
            'creation_receipt': obj({'plan_id': TEXT, 'path': TEXT,
                'before': enum('NOT_EXISTS', 'SAME_PLAN', 'EXISTING'),
                'status': enum('CREATED', 'RESUMED', 'EXISTING'),
                'observed_at': TEXT, 'request_ref': TEXT}),
        }),
        'documents': array(obj({'role': enum(*ROLE_SECTIONS), 'draft_id': TEXT,
                               'sections': array(obj({'id': TEXT, 'heading': TEXT}), 1)}), 5),
        'phases': array(obj({'id': INTEGER, 'status': enum('PLANNED', 'COMPLETE', 'NOT_APPLICABLE', 'BLOCKED'),
                            'required': BOOLEAN, 'evidence': strings, 'reason': TEXT}), 10),
        'discovery': obj({
            'status': enum('COMPLETE', 'PARTIAL', 'NOT_APPLICABLE'), 'reason': TEXT,
            'inventory': array(obj({'id': TEXT, 'kind': TEXT, 'required': BOOLEAN,
                'status': enum('AVAILABLE', 'UNAVAILABLE'), 'reference': TEXT})),
            'queries': strings, 'receipts': array(ref),
            'reads': array(obj({'source_id': TEXT, 'depth': enum('full', 'partial', 'summary-only', 'unread'),
                'reference': TEXT, 'unit': enum('lines', 'messages', 'bytes'), 'total': INTEGER,
                'content_sha256': DIGEST, 'capture': ref,
                'ranges': array(obj({'start': INTEGER, 'end': INTEGER}))})),
            'limitations': strings,
        }),
        'features': array(obj({'id': TEXT, 'description': TEXT,
            'requirement_ids': array(TEXT, 1), 'source_ids': array(TEXT, 1),
            'acceptance': array(TEXT, 1),
            'settings': array(obj({'name': TEXT, 'behavior': TEXT, 'acceptance': array(TEXT, 1)})),
            'settings_reason': TEXT}), 1),
        'decisions': obj({
            'events': array(obj({'id': TEXT, 'action_id': TEXT,
                'state': enum('PLANNED', 'PENDING_APPROVAL', 'APPROVED', 'REJECTED', 'REVOKED', 'COMPLETED', 'NOT_APPLICABLE'),
                'reference': TEXT, 'observed_at': TEXT})),
            'current': array(obj({'action_id': TEXT, 'state': TEXT, 'event_id': TEXT})),
        }),
        'review': obj({'status': enum('NOT_RUN', 'PENDING', 'ACCEPTED', 'CHANGES_REQUIRED', 'PARTIAL'),
            'reviewer_id': STRING, 'author_id': TEXT, 'revision': TEXT,
            'snapshot_sha256': STRING,
            'areas': array(obj({'id': TEXT, 'status': enum('PASS', 'FAIL', 'UNVERIFIED', 'N/A'),
                                'evidence': strings, 'reason': TEXT})),
            'changed_ids': strings, 'affected_areas': strings}),
        'package': obj({'mode': enum('none', 'local_adapter', 'knowledge_bundle'),
            'status': enum('NOT_APPLICABLE', 'PLANNED', 'PACKAGED', 'INSTALLED', 'LOAD_VERIFIED'),
            'root': STRING, 'reason': TEXT,
            'inventory': array(obj({'role': TEXT, 'source_root': TEXT, 'path': TEXT,
                'package_path': STRING, 'disposition': enum('included', 'external', 'excluded'),
                'required': BOOLEAN, 'sha256': DIGEST, 'reason': TEXT})),
            'fresh_session_evidence': strings}),
        'evidence_policy': obj({'authorized': BOOLEAN, 'approval_ref': STRING,
            'paths': strings,
            'record_types': array(enum('review_receipt', 'command_exit', 'digest', 'timestamp', 'terminal_state')),
            'prefixes': array(obj({'path': TEXT, 'length': INTEGER, 'sha256': DIGEST}))}),
        'gitnexus': obj({'applicability': enum('N/A', 'REQUIRED'), 'tool_id': STRING, 'reason': TEXT}),
        'issues': array(obj({'id': TEXT, 'severity': enum('P0', 'P1', 'P2'), 'required': BOOLEAN,
                             'phase': INTEGER, 'status': enum('OPEN', 'RESOLVED'), 'reference': TEXT, 'reason': TEXT})),
    }
    from workflow_effects import effects_schema
    properties['effects'] = effects_schema()
    return obj(properties)


def _shape(value, schema, where):
    if 'enum' in schema and value not in schema['enum']:
        raise PacketError(where + ': unsupported value')
    kind = schema.get('type')
    good = {'object': lambda x: isinstance(x, dict), 'array': lambda x: isinstance(x, list),
            'string': lambda x: isinstance(x, str), 'integer': lambda x: type(x) is int,
            'boolean': lambda x: type(x) is bool}
    if kind and not good[kind](value):
        raise PacketError(where + ': expected ' + kind)
    if kind == 'object':
        if set(schema['required']) - set(value):
            raise PacketError(where + ': missing ' + ', '.join(sorted(set(schema['required']) - set(value))))
        if set(value) - set(schema['properties']):
            raise PacketError(where + ': unsupported fields')
        for key, child in value.items():
            _shape(child, schema['properties'][key], where + '.' + key)
    elif kind == 'array':
        if len(value) < schema.get('minItems', 0):
            raise PacketError(where + ': too few items')
        for index, child in enumerate(value):
            _shape(child, schema['items'], f'{where}[{index}]')
    elif kind == 'string':
        if len(value) < schema.get('minLength', 0) or ('pattern' in schema and not re.search(schema['pattern'], value)):
            raise PacketError(where + ': invalid string')
    elif kind == 'integer' and value < schema.get('minimum', 0):
        raise PacketError(where + ': invalid count')


def _unique(rows, field, where):
    ids = [row[field] for row in rows]
    if len(ids) != len(set(ids)):
        raise PacketError(where + ': duplicate ' + field)
    return set(ids)


def _timestamp(value, where):
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if parsed.tzinfo is None:
            raise ValueError()
    except (AttributeError, ValueError, TypeError):
        raise PacketError(where + ': timezone-qualified ISO timestamp required') from None


def validate_workflow_structure(plan):
    _shape(plan.get('workflow'), workflow_schema(), 'workflow')
    w = plan['workflow']
    _unique(w['issues'], 'id', 'issues')
    if any(issue['phase'] > 9 for issue in w['issues']):
        raise PacketError('issue phase must be 0 through 9')
    roots = w['roots']
    for name, path in [('docs_root', roots['docs_root'])] + [(r['id'], r['path']) for r in roots['source_roots']]:
        if not Path(path).is_absolute():
            raise PacketError('workflow.roots.' + name + ': canonical absolute path required')
    root_ids = _unique(roots['source_roots'], 'id', 'source_roots')
    if 'docs' in root_ids:
        raise PacketError('source_roots id docs is reserved')
    _timestamp(roots['creation_receipt']['observed_at'], 'creation_receipt.observed_at')
    docs = w['documents']
    if _unique(docs, 'role', 'documents') != set(ROLE_SECTIONS):
        raise PacketError('five mandatory document roles must each appear exactly once')
    _unique(docs, 'draft_id', 'documents')
    drafts = {d['id']: d for d in plan['drafts']}
    for doc in docs:
        draft = drafts.get(doc['draft_id'])
        if draft is None or not draft['required']:
            raise PacketError('mandatory document role must map to a required draft: ' + doc['role'])
        expected_kind = 'specification' if doc['role'] == 'specification' else 'document'
        if draft['kind'] != expected_kind:
            raise PacketError('governance document role cannot map to a native agent: ' + doc['role'])
        if Path(draft['target']).suffix.casefold() != '.md' or draft['target'].split('/')[0].casefold() in ('agents', '.agents', '.codex', '.zcode', '.claude'):
            raise PacketError('governance role requires a normal project Markdown path')
        if _unique(doc['sections'], 'id', doc['role']) != set(ROLE_SECTIONS[doc['role']]):
            raise PacketError('required section IDs missing or unexpected: ' + doc['role'])
        normalized = [re.sub(r'\s+', ' ', section['heading']).strip().casefold() for section in doc['sections']]
        if len(normalized) != len(set(normalized)):
            raise PacketError('document section headings must be distinct: ' + doc['role'])
    phases = w['phases']
    if _unique(phases, 'id', 'phases') != set(range(10)):
        raise PacketError('phases 0 through 9 must each appear exactly once')
    if any(not p['required'] for p in phases if p['id'] in (0, 1, 2, 3, 4, 5, 8, 9)):
        raise PacketError('core workflow phases cannot be optional')
    _unique(w['discovery']['inventory'], 'id', 'discovery.inventory')
    _unique(w['discovery']['reads'], 'source_id', 'discovery.reads')
    for record in w['discovery']['reads']:
        if record['source_id'] not in {s['id'] for s in plan['sources']}:
            raise PacketError('reading record references unknown source')
        for span in record['ranges']:
            if span['start'] < 1 or span['end'] < span['start'] or span['end'] > record['total']:
                raise PacketError('invalid reading range')
    req_schema = obj({'id': TEXT, 'text': TEXT, 'acceptance': array(TEXT, 1), 'source_ids': array(TEXT, 1)})
    for row in plan['requirements']:
        _shape(row, req_schema, 'requirements')
    if not plan['requirements']:
        raise PacketError('requirements cannot be empty')
    reqs = _unique(plan['requirements'], 'id', 'requirements')
    sources = {s['id'] for s in plan['sources']}
    if not sources:
        raise PacketError('requirements need real source references')
    features = _unique(w['features'], 'id', 'features')
    covered = set()
    for requirement in plan['requirements']:
        if set(requirement['source_ids']) - sources:
            raise PacketError('requirement references unknown source')
    for feature in w['features']:
        if set(feature['requirement_ids']) - reqs or set(feature['source_ids']) - sources:
            raise PacketError('feature references unknown requirement/source')
        covered.update(feature['requirement_ids'])
    if covered != reqs:
        raise PacketError('requirements missing feature/setting acceptance mapping')
    events = w['decisions']['events']
    _unique(events, 'id', 'decision events')
    current = w['decisions']['current']
    _unique(current, 'action_id', 'decision current')
    latest = {}
    for event in events:
        _timestamp(event['observed_at'], 'decision.observed_at')
        latest[event['action_id']] = event
    if set(latest) != {r['action_id'] for r in current}:
        raise PacketError('decision current must cover every action')
    for row in current:
        event = latest[row['action_id']]
        if row['state'] != event['state'] or row['event_id'] != event['id']:
            raise PacketError('contradictory current decision state: ' + row['action_id'])
    review = w['review']
    _unique(review['areas'], 'id', 'review.areas')
    if set(review['affected_areas']) - set(REVIEW_AREAS) - {'gitnexus'}:
        raise PacketError('unknown affected review area')
    policy = w['evidence_policy']
    _unique(policy['prefixes'], 'path', 'evidence prefixes')
    for path in policy['paths'] + [row['path'] for row in policy['prefixes']]:
        _relative(path, 'evidence path')
    terminal_paths = {drafts[d['draft_id']]['target'] for d in docs if d['role'] in ('project_status', 'memory')}
    if any(path not in terminal_paths and not path.startswith(('evidence/', 'docs/evidence/')) for path in policy['paths']):
        raise PacketError('evidence recording paths are limited to status/memory and explicit evidence directories')
    if policy['authorized'] and (not policy['approval_ref'].strip() or not policy['paths'] or not policy['record_types']):
        raise PacketError('authorized evidence recording requires bounded paths/types and actual approval reference')
    if not policy['authorized'] and (policy['paths'] or policy['record_types']):
        raise PacketError('unauthorized evidence policy must not grant writes')
    g6 = w['gitnexus']
    if plan['host'] == 'zcode':
        if g6['applicability'] != 'N/A' or g6['tool_id']:
            raise PacketError('ZCode has no GitNexus requirement; G6 must be N/A without probing')
    else:
        if g6['applicability'] != 'REQUIRED' or g6['tool_id'] != 'gitnexus-project-onboarding':
            raise PacketError('Codex requires its GitNexus tool decision row')
        rows = [t for t in plan['tools'] if isinstance(t, dict) and t.get('id') == g6['tool_id']]
        if len(rows) != 1:
            raise PacketError('Codex requires exactly one authoritative GitNexus tool row')
    tool_kinds = ('SKILL', 'MCP', 'CLI', 'native_agent', 'Plugin')
    for kind in tool_kinds:
        matches = [t for t in plan['tools'] if isinstance(t, dict) and t.get('kind') == kind]
        if len(matches) != 1 or matches[0].get('decision') not in ('adopt', 'reuse', 'N/A') or not str(matches[0].get('reason', '')).strip():
            raise PacketError('tool decision required exactly once: ' + kind)
    for source in plan['sources']:
        if not isinstance(source.get('root_id', 'docs'), str):
            raise PacketError('source.root_id must be string')
        if source.get('root_id', 'docs') not in root_ids | {'docs'}:
            raise PacketError('source references unknown root_id')
    package = w['package']
    for item in package['inventory']:
        if item['source_root'] not in root_ids | {'docs'}:
            raise PacketError('package source_root unknown')
        _relative(item['path'], 'package source path')
        if item['disposition'] == 'included':
            _relative(item['package_path'], 'package path')
        elif not item['reason'].strip():
            raise PacketError('external/excluded package item requires reason')
    if package['root'] and not Path(package['root']).is_absolute():
        raise PacketError('package.root must be absolute')
    from workflow_effects import validate_effects_structure
    validate_effects_structure(plan)


def source_location(plan, project, source):
    """Resolve a known source root without treating external code as DOCS_ROOT."""
    if plan.get('schema_version') != '2.0':
        return resolve_inside(project, source['path'])
    roots = plan['workflow']['roots']
    locations = {'docs': roots['docs_root'], **{r['id']: r['path'] for r in roots['source_roots']}}
    identifier = source.get('root_id', 'docs')
    if identifier not in locations:
        raise PacketError('unknown source root: ' + identifier)
    location = resolve_inside(locations[identifier], source['path'])
    if not location.exists():
        from workflow_effects import preserved_source_location
        archived = preserved_source_location(plan, project, source)
        if archived is not None:
            return archived
    return location


def workflow_snapshot(plan, project):
    """Identity of stable output bytes and reviewed terminal prefixes, no self hash."""
    w = plan['workflow']
    terminal = {d['draft_id'] for d in w['documents'] if d['role'] in ('independent_review', 'project_status', 'memory')}
    stable = [{'id': d['id'], 'target': d['target'], 'sha256': d['expected_sha256']}
              for d in plan['drafts'] if d['id'] not in terminal]
    review_id = next(d['draft_id'] for d in w['documents'] if d['role'] == 'independent_review')
    review_target = next(d['target'] for d in plan['drafts'] if d['id'] == review_id)
    package = dict(w['package'])
    package['inventory'] = [({key: value for key, value in item.items() if key != 'sha256'}
                             if item['role'] == 'independent_review' and item['source_root'] == 'docs'
                             and item['path'] == review_target else dict(item))
                            for item in package['inventory']]
    sources = [{**source, 'required': source.get('required', True)} for source in plan['sources']]
    packet_material = {key: value for key, value in plan.items() if key not in ('workflow', 'drafts')}
    packet_material['sources'] = sources
    draft_material = [({key: value for key, value in draft.items() if key not in ('sha256', 'expected_sha256')}
                       if draft['id'] == review_id else dict(draft)) for draft in plan['drafts']]
    workflow_material = {key: value for key, value in w.items() if key not in ('review', 'phases', 'package')}
    workflow_material['package'] = package
    workflow_material['phases'] = [
        ({'id': p['id'], 'required': p['required'], 'reason': p['reason']}
         if p['id'] in (5, 8, 9) else dict(p)) for p in w['phases']]
    return {'plan_id': plan['plan_id'], 'revision': plan['revision'], 'host': plan['host'],
            'docs_root': w['roots']['docs_root'],
            'source_roots': w['roots']['source_roots'],
            'outputs': sorted(stable, key=lambda d: d['id']),
            'prefixes': sorted(w['evidence_policy']['prefixes'], key=lambda d: d['path']),
            'material_scope': {'packet': packet_material, 'drafts': draft_material, 'workflow': workflow_material}}


def workflow_snapshot_digest(plan, project):
    return packet_digest(workflow_snapshot(plan, project))


def workflow_findings(plan, project, stage='plan'):
    """Check current artifacts. Returns errors instead of granting permissions."""
    if stage not in ('plan', 'completion'):
        raise PacketError('workflow stage must be plan or completion')
    findings = []
    def fail(code, message):
        findings.append({'severity': 'error', 'code': code, 'message': message})
    try:
        validate_workflow_structure(plan)
    except (PacketError, KeyError, TypeError, ValueError) as exc:
        fail('W_STRUCTURE', str(exc))
        return findings
    w = plan['workflow']
    for issue in w['issues']:
        if (stage == 'completion' or issue['phase'] <= 4) and issue['status'] == 'OPEN' and (issue['severity'] == 'P0' or (issue['severity'] == 'P1' and issue['required'])):
            fail('W_ISSUE', 'required issue remains open: ' + issue['id'])
    roots = w['roots']
    if Path(roots['docs_root']).resolve() != Path(project).resolve():
        fail('W_ROOT', 'actual project root differs from canonical docs_root')
    receipt = roots['creation_receipt']
    if receipt['plan_id'] != plan['plan_id'] or Path(receipt['path']).resolve() != Path(project).resolve() or not Path(project).is_dir():
        fail('W_DESTINATION', 'destination creation receipt does not identify the actual plan/root')
    if roots['destination_mode'] == 'new_folder' and (receipt['before'], receipt['status']) not in (('NOT_EXISTS', 'CREATED'), ('SAME_PLAN', 'RESUMED')):
        fail('W_DESTINATION', 'new_folder requires creation or same-plan resume receipt')
    bodies = {}
    for doc in w['documents']:
        draft = next(d for d in plan['drafts'] if d['id'] == doc['draft_id'])
        try:
            body = expected_content(draft, read_draft(project, draft)).decode('utf-8')
            bodies[doc['role']] = body
            headings = {re.sub(r'\s+#+\s*$', '', m.group(1)).strip().casefold()
                        for m in re.finditer(r'^#{1,6}\s+(.+)$', body, re.M)}
            for section in doc['sections']:
                if section['heading'].casefold() not in headings:
                    fail('W_CONTENT', doc['role'] + ' missing declared section: ' + section['heading'])
                elif not _section_content(body, section['heading']):
                    fail('W_CONTENT', doc['role'] + ' has empty declared section: ' + section['heading'])
            if re.search(r'\{\{[^}]+\}\}|\bTODO\b|\bTBD\b|<fill[^>]*>', body, re.I):
                fail('W_CONTENT', doc['role'] + ' contains unfilled template placeholders')
            if _angle_placeholders(body):
                fail('W_CONTENT', doc['role'] + ' contains unfilled uppercase angle placeholders')
            if stage == 'completion':
                target = resolve_inside(project, draft['target'])
                if not target.is_file():
                    fail('W_OUTPUT', 'formal required document missing: ' + draft['target'])
                elif doc['role'] not in ('project_status', 'memory') and sha256(target.read_bytes()) != draft['expected_sha256']:
                    fail('W_OUTPUT', 'formal document differs from approved expected bytes: ' + draft['target'])
        except (PacketError, OSError, UnicodeError) as exc:
            fail('W_CONTENT', str(exc))
    for requirement in plan['requirements']:
        if requirement['id'] not in bodies.get('specification', ''):
            fail('W_TRACEABILITY', 'specification omits requirement ID: ' + requirement['id'])
    for feature in w['features']:
        if feature['id'] not in bodies.get('specification', ''):
            fail('W_TRACEABILITY', 'specification omits feature ID: ' + feature['id'])
    for source in plan['sources']:
        if source.get('kind') == 'file' or 'path' in source:
            try:
                location = source_location(plan, project, source)
                observed = sha256(location.read_bytes())
                promoted = any(location == resolve_inside(project, d['target'])
                               and source['sha256'] == d['baseline_sha256']
                               and observed == d['expected_sha256'] for d in plan['drafts'])
                if observed != source['sha256'] and not promoted:
                    fail('W_SOURCE', 'source bytes changed: ' + source['id'])
            except (OSError, PacketError) as exc:
                fail('W_SOURCE', str(exc))
        if source.get('required', True) and source.get('depth') != 'full':
            fail('W_COVERAGE', 'required source is not fully read: ' + source['id'])
    discovery = w['discovery']
    if plan['route'] == 'reorg' and discovery['status'] == 'NOT_APPLICABLE':
        fail('W_DISCOVERY', 'reorg requires global discovery inventory/receipts, not N/A')
    if discovery['status'] == 'PARTIAL':
        fail('W_DISCOVERY', 'required historical discovery remains partial')
    if discovery['status'] == 'COMPLETE':
        if not discovery['inventory'] or not discovery['queries'] or not discovery['receipts']:
            fail('W_DISCOVERY', 'complete discovery needs inventory, query groups and tool receipt files')
        if any(row['required'] and row['status'] != 'AVAILABLE' for row in discovery['inventory']):
            fail('W_DISCOVERY', 'required historical source unavailable')
        observed = set()
        for reference in discovery['receipts']:
            try:
                raw = source_location(plan, project, reference).read_bytes()
                if sha256(raw) != reference['sha256']:
                    raise PacketError('discovery receipt hash mismatch')
                data = json.loads(raw.decode('utf-8'))
                if not isinstance(data, dict):
                    raise PacketError('discovery receipt must be an object')
                if data.get('schema_version') != 'open-project/discovery-receipt/2.0' or data.get('status') != 'COMPLETE':
                    raise PacketError('discovery receipt missing complete normalized tool result')
                if (not isinstance(data.get('source_inventory'), list) or not data['source_inventory']
                        or not isinstance(data.get('census'), dict) or not data['census']
                        or not isinstance(data.get('query_groups'), list) or not data['query_groups']
                        or not isinstance(data.get('pagination'), dict) or not isinstance(data.get('snapshot'), dict)):
                    raise PacketError('discovery receipt lacks inventory/census/query groups')
                if data.get('complete_scope') != 'supplied_sources_only' or data.get('all_system_history_complete') is not False:
                    raise PacketError('tool receipt must distinguish supplied sources from all-system history')
                for row in data['source_inventory']:
                    if not isinstance(row, dict) or not isinstance(row.get('source_id'), str) or not row['source_id'].strip() or row.get('status') not in ('AVAILABLE', 'UNAVAILABLE'):
                        raise PacketError('invalid discovery source inventory entry')
                    if row['status'] == 'AVAILABLE':
                        observed.add(row['source_id'])
                _timestamp(data['snapshot'].get('t0'), 'discovery snapshot.t0')
                _timestamp(data['snapshot'].get('t1'), 'discovery snapshot.t1')
                for count in data.get('census', {}).values():
                    if not isinstance(count, dict):
                        raise PacketError('discovery census entry must be object')
                    for key in ('total', 'eligible', 'scanned', 'skipped', 'error_rows', 'matched', 'unscanned'):
                        if type(count.get(key)) is not int or count[key] < 0:
                            raise PacketError('invalid discovery census')
                    if count['total'] != count['eligible'] or count['eligible'] != count['scanned'] + count['unscanned'] or count['matched'] > count['scanned'] - count['skipped'] or count['unscanned'] or count['error_rows']:
                        raise PacketError('incomplete or contradictory discovery census')
                ends = data.get('pagination', {}).get('end_reached', {})
                if not isinstance(ends, dict) or set(ends) != set(data['census']) or not all(value is True for value in ends.values()):
                    raise PacketError('discovery pagination not exhausted')
            except (OSError, PacketError, UnicodeError, json.JSONDecodeError, KeyError, TypeError) as exc:
                fail('W_DISCOVERY', str(exc))
        if {r['id'] for r in discovery['inventory'] if r['required']} - observed:
            fail('W_DISCOVERY', 'required inventory source has no normalized tool receipt')
    reads = {r['source_id']: r for r in discovery['reads']}
    for source in plan['sources']:
        if source.get('kind') == 'session' and source.get('required', True):
            read = reads.get(source['id'])
            if not read or read['depth'] != 'full' or not read['ranges']:
                fail('W_COVERAGE', 'required session lacks full reading range evidence: ' + source['id'])
    for read in discovery['reads']:
        try:
            raw = source_location(plan, project, read['capture']).read_bytes()
            if sha256(raw) != read['capture']['sha256'] or read['content_sha256'] != read['capture']['sha256']:
                raise PacketError('reading capture hash differs from observed content identity')
            source = next(s for s in plan['sources'] if s['id'] == read['source_id'])
            if source.get('content_sha256') != read['content_sha256']:
                raise PacketError('source content_sha256 does not identify reading capture')
            if read['unit'] == 'bytes':
                observed_total = len(raw)
            elif read['unit'] == 'lines':
                observed_total = len(raw.decode('utf-8').splitlines())
            else:
                messages = json.loads(raw.decode('utf-8'))
                if not isinstance(messages, list):
                    raise PacketError('message reading capture must be a JSON array')
                observed_total = len(messages)
            if observed_total != read['total']:
                raise PacketError('reading capture total differs from declared units')
            if read['depth'] == 'full':
                cursor = 1
                for span in sorted(read['ranges'], key=lambda row: row['start']):
                    if span['start'] > cursor:
                        raise PacketError('full reading ranges leave gaps')
                    cursor = max(cursor, span['end'] + 1)
                if read['total'] < 1 or cursor != read['total'] + 1:
                    raise PacketError('full reading ranges do not cover the capture')
        except (OSError, PacketError, UnicodeError, json.JSONDecodeError, StopIteration) as exc:
            fail('W_COVERAGE', str(exc))
    for phase in w['phases']:
        due = phase['id'] <= 4 or stage == 'completion'
        if due and phase['required'] and (phase['status'] != 'COMPLETE' or not phase['evidence']):
            fail('W_PHASE', 'required phase incomplete or unproved: ' + str(phase['id']))
    adopted = [tool for tool in plan['tools'] if isinstance(tool, dict) and tool.get('kind') in ('SKILL', 'MCP', 'CLI', 'native_agent', 'Plugin') and tool.get('decision') == 'adopt']
    if adopted and not next(p for p in w['phases'] if p['id'] == 6)['required']:
        fail('W_PHASE', 'adopted tool implementation/verification phase cannot be optional')
    for tool in adopted:
        if tool['kind'] == 'Plugin':
            continue  # Its typed package inventory is the artifact contract.
        artifacts = tool.get('artifacts')
        if not isinstance(artifacts, list) or not artifacts:
            fail('W_TOOL', 'adopted tool requires definition drafts or captured artifact refs: ' + tool['kind'])
            continue
        for artifact in artifacts:
            try:
                if not isinstance(artifact, dict):
                    raise PacketError('tool artifact must be a typed reference')
                if set(artifact) == {'draft_id'}:
                    definition = next((d for d in plan['drafts'] if d['id'] == artifact['draft_id']), None)
                    if definition is None:
                        raise PacketError('tool artifact points to unknown draft')
                    if tool['kind'] == 'native_agent' and definition['kind'] != plan['host'] + '-agent':
                        raise PacketError('native agent adoption requires its native definition draft')
                    if tool['kind'] == 'SKILL' and Path(definition['target']).name != 'SKILL.md':
                        raise PacketError('Skill adoption requires a SKILL.md definition draft')
                    if stage == 'completion':
                        actual = resolve_inside(project, definition['target']).read_bytes()
                        if not actual.strip() or sha256(actual) != definition['expected_sha256']:
                            raise PacketError('adopted tool definition is not implemented at expected bytes')
                elif set(artifact) == {'root_id', 'path', 'sha256'}:
                    _hash(artifact['sha256'], 'tool artifact.sha256')
                    actual = source_location(plan, project, artifact).read_bytes()
                    if not actual.strip() or sha256(actual) != artifact['sha256']:
                        raise PacketError('captured tool artifact hash differs or artifact is empty')
                    if tool['kind'] == 'SKILL' and Path(artifact['path']).name != 'SKILL.md':
                        raise PacketError('captured Skill artifact must be its SKILL.md')
                    if tool['kind'] == 'native_agent' and Path(artifact['path']).suffix.casefold() != ('.md' if plan['host'] == 'zcode' else '.toml'):
                        raise PacketError('captured native agent artifact uses the wrong host format')
                else:
                    raise PacketError('tool artifact must reference a draft or a root-qualified captured file')
            except (PacketError, OSError, TypeError) as exc:
                fail('W_TOOL', str(exc))
    package = w['package']
    plugin = next(t for t in plan['tools'] if isinstance(t, dict) and t.get('kind') == 'Plugin')
    if plugin['decision'] == 'adopt' and package['mode'] == 'none':
        fail('W_PACKAGE', 'adopted Plugin contradicts package mode none')
    if plugin['decision'] == 'N/A' and package['mode'] != 'none':
        fail('W_PACKAGE', 'package scope contradicts Plugin decision N/A')
    if package['mode'] != 'none' and not next(p for p in w['phases'] if p['id'] == 7)['required']:
        fail('W_PHASE', 'adopted package phase cannot be optional')
    if package['mode'] == 'none' and package['status'] != 'NOT_APPLICABLE':
        fail('W_PACKAGE', 'no package mode must remain explicitly N/A')
    if package['mode'] != 'none':
        if not package['inventory']:
            fail('W_PACKAGE', 'adopted package requires inventory')
        if stage == 'completion' and package['status'] not in ('PACKAGED', 'INSTALLED', 'LOAD_VERIFIED'):
            fail('W_PACKAGE', 'adopted package has not been packaged')
        if package['status'] == 'LOAD_VERIFIED' and not package['fresh_session_evidence']:
            fail('W_PACKAGE', 'LOAD_VERIFIED requires fresh-session evidence')
        if package['mode'] == 'knowledge_bundle':
            bundled_roles = {i['role'] for i in package['inventory'] if i['disposition'] == 'included' and i['required']}
            if set(ROLE_SECTIONS) - bundled_roles:
                fail('W_PACKAGE', 'knowledge bundle omits mandatory document roles: ' + ', '.join(sorted(set(ROLE_SECTIONS) - bundled_roles)))
        included = set()
        for item in package['inventory']:
            if item['role'] in ROLE_SECTIONS:
                mapped_id = next(d['draft_id'] for d in w['documents'] if d['role'] == item['role'])
                mapped = next(d for d in plan['drafts'] if d['id'] == mapped_id)
                if item['source_root'] != 'docs' or item['path'] != mapped['target']:
                    fail('W_PACKAGE', 'package document role does not identify its formal document: ' + item['role'])
            if package['mode'] == 'knowledge_bundle' and item['required'] and item['disposition'] != 'included':
                fail('W_PACKAGE', 'required knowledge bundle item is not included: ' + item['role'])
            if item['disposition'] == 'included':
                if item['package_path'].casefold() in included:
                    fail('W_PACKAGE', 'duplicate package path')
                included.add(item['package_path'].casefold())
                if stage == 'completion':
                    try:
                        original = source_location(plan, project, {'root_id': item['source_root'], 'path': item['path']}).read_bytes()
                        packed = resolve_inside(package['root'], item['package_path']).read_bytes()
                        if sha256(original) != item['sha256'] or sha256(packed) != item['sha256']:
                            fail('W_PACKAGE', 'package bytes differ from inventory: ' + item['package_path'])
                    except (OSError, PacketError) as exc:
                        fail('W_PACKAGE', str(exc))
    review = w['review']
    if review['status'] == 'ACCEPTED' or stage == 'completion':
        if review['status'] != 'ACCEPTED' or not review['reviewer_id'] or review['reviewer_id'] == review['author_id']:
            fail('W_REVIEW', 'independent accepted review required')
        if review['revision'] != plan['revision'] or review['snapshot_sha256'] != workflow_snapshot_digest(plan, project):
            fail('W_REVIEW', 'review does not cover current revision/output snapshot')
        areas = {r['id']: r for r in review['areas']}
        required_areas = set(REVIEW_AREAS) | ({'gitnexus'} if plan['host'] == 'codex' else set())
        if required_areas - set(areas):
            fail('W_REVIEW', 'review lacks required areas')
        for area in review['areas']:
            if area['status'] not in ('PASS', 'N/A') or not area['evidence']:
                fail('W_REVIEW', 'review area unresolved or unproved: ' + area['id'])
        report = bodies.get('independent_review', '')
        if (not re.search(r'(?im)^\s*(?:status|current status|狀態|結論)\s*[:：=]\s*ACCEPTED\s*$', report)
                or not review['reviewer_id'] or review['reviewer_id'] not in report
                or not review['snapshot_sha256'] or review['snapshot_sha256'] not in report):
            fail('W_REVIEW', 'actual review report must record ACCEPTED, reviewer identity and current snapshot')
        if re.search(r'(?im)^\s*(?:status|current status|狀態|結論)\s*[:：=]\s*(?:NOT_RUN|PENDING|REVIEW_PENDING)\s*$', report):
            fail('W_REVIEW', 'review report still declares current review unexecuted')
    if stage == 'completion':
        for row in plan['unknowns']:
            if isinstance(row, dict) and row.get('required') is True and row.get('status') not in ('RESOLVED', 'VERIFIED'):
                fail('W_COVERAGE', 'explicit required unknown remains unresolved: ' + str(row.get('id', 'unknown')))
        prefix_paths = {p['path'] for p in w['evidence_policy']['prefixes']}
        terminal = {d['draft_id'] for d in w['documents'] if d['role'] in ('project_status', 'memory')}
        if {d['target'] for d in plan['drafts'] if d['id'] in terminal} - prefix_paths:
            fail('W_EVIDENCE', 'review snapshot must cover status and memory prefixes')
        for draft in plan['drafts']:
            if draft['id'] in terminal:
                path = resolve_inside(project, draft['target'])
                declared = next((p for p in w['evidence_policy']['prefixes'] if p['path'] == draft['target']), None)
                expected = expected_content(draft, read_draft(project, draft))
                if declared and (declared['length'] != len(expected) or declared['sha256'] != draft['expected_sha256']):
                    fail('W_EVIDENCE', 'reviewed terminal prefix must cover full approved document: ' + draft['target'])
                if path.is_file() and sha256(path.read_bytes()) != draft['expected_sha256'] and draft['target'] not in prefix_paths:
                    fail('W_EVIDENCE', 'terminal document changed without bounded prefix: ' + draft['target'])
        for prefix in w['evidence_policy']['prefixes']:
            try:
                content = resolve_inside(project, prefix['path']).read_bytes()
                if len(content) < prefix['length'] or sha256(content[:prefix['length']]) != prefix['sha256']:
                    fail('W_EVIDENCE', 'reviewed evidence prefix changed: ' + prefix['path'])
                if len(content) > prefix['length'] and not w['evidence_policy']['authorized']:
                    fail('W_EVIDENCE', 'terminal append lacks explicit evidence authorization')
                elif len(content) > prefix['length']:
                    if prefix['path'] not in w['evidence_policy']['paths']:
                        raise PacketError('terminal append path is outside evidence authorization')
                    _check_terminal_tail(content[prefix['length']:], w['evidence_policy'])
            except (OSError, PacketError) as exc:
                fail('W_EVIDENCE', str(exc))
    from workflow_effects import effects_findings
    findings.extend(effects_findings(plan, project, stage))
    from workflow_package import package_findings
    findings.extend(package_findings(plan, project, stage))
    return findings


def _angle_placeholders(body):
    """Keep literal command/code examples; flag known template tokens in prose."""
    lines, fence = [], None
    for line in body.splitlines():
        marker = re.match(r'^\s*(`{3,}|~{3,})', line)
        if marker:
            token = marker.group(1)
            if fence is None:
                fence = (token[0], len(token))
            elif token[0] == fence[0] and len(token) >= fence[1]:
                fence = None
            continue
        if fence is None:
            lines.append(line)
    prose = '\n'.join(lines)
    prose = re.sub(r'(`+).*?\1', '', prose)
    prose = re.sub(r'(?is)<(?:code|pre)\b[^>]*>.*?</(?:code|pre)>', '', prose)
    html_tags = set(('A ABBR ADDRESS ARTICLE ASIDE AUDIO B BLOCKQUOTE BODY BR BUTTON CANVAS '
                     'CAPTION CODE COL COLGROUP DATA DATALIST DD DEL DETAILS DFN DIV DL DT '
                     'EM FIELDSET FIGCAPTION FIGURE FOOTER FORM G H1 H2 H3 H4 H5 H6 HEAD HEADER '
                     'HR HTML I IFRAME IMG INPUT LABEL LEGEND LI LINK MAIN MARK META NAV '
                     'OL OPTGROUP OPTION OUTPUT P PATH PICTURE PRE PROGRESS Q S SAMP SCRIPT '
                     'SECTION SELECT SMALL SOURCE SPAN STRONG STYLE SUB SUMMARY SUP SVG '
                     'TABLE TBODY TD TEMPLATE TEXTAREA TFOOT TH THEAD TIME TITLE TR TRACK '
                     'U UL VAR VIDEO WBR').split())
    return any(token.split()[0] not in html_tags
               for token in re.findall(r'<([A-Z][A-Z0-9_ -]*)>', prose))


def _section_content(body, heading):
    matches = list(re.finditer(r'^(#{1,6})\s+(.+)$', body, re.M))
    for index, match in enumerate(matches):
        title = re.sub(r'\s+#+\s*$', '', match.group(2)).strip()
        if title.casefold() != heading.casefold():
            continue
        end = len(body)
        for next_match in matches[index + 1:]:
            if len(next_match.group(1)) <= len(match.group(1)):
                end = next_match.start()
                break
        content = body[match.end():end]
        content = re.sub(r'(?s)<!--.*?-->', '', content)
        content = re.sub(r'^#{1,6}.*$', '', content, flags=re.M)
        content = re.sub(r'<[^>]*>', '', content)
        return bool(re.search(r'\w', content))
    return False


def _check_terminal_tail(raw, policy):
    """The bounded append channel contains typed JSONL receipts, not free edits."""
    shapes = {
        'review_receipt': obj({'type': enum('review_receipt'), 'reviewer_id': TEXT, 'reference': TEXT, 'snapshot_sha256': DIGEST}),
        'command_exit': obj({'type': enum('command_exit'), 'command': TEXT, 'exit_code': {'type': 'integer', 'minimum': -2147483648}, 'observed_at': TEXT}),
        'digest': obj({'type': enum('digest'), 'path': TEXT, 'sha256': DIGEST}),
        'timestamp': obj({'type': enum('timestamp'), 'value': TEXT}),
        'terminal_state': obj({'type': enum('terminal_state'), 'value': enum('COMPLETE', 'PARTIAL', 'BLOCKED', 'REVIEW_PENDING'), 'reference': TEXT}),
    }
    try:
        lines = raw.decode('utf-8').splitlines()
        records = [json.loads(line) for line in lines if line.strip()]
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise PacketError('terminal append must contain typed JSONL receipt records') from exc
    if not records:
        raise PacketError('terminal append contains no receipt records')
    for record in records:
        if not isinstance(record, dict) or record.get('type') not in policy['record_types']:
            raise PacketError('terminal append record type is outside evidence authorization')
        _shape(record, shapes[record['type']], 'terminal receipt')
        if record['type'] == 'timestamp':
            _timestamp(record['value'], 'terminal timestamp')
        if record['type'] == 'command_exit':
            _timestamp(record['observed_at'], 'terminal command timestamp')
