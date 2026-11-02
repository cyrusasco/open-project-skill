"""Synthetic packet 2 fixtures. No real projects, sessions, adapters or approvals."""
from pathlib import Path
from datetime import datetime, timezone
import json


def make_workflow_packet(project, host='zcode', complete=False):
    from plan_contract import DRAFT_MARKER, expected_content, sha256
    from workflow_contract import ROLE_SECTIONS, REVIEW_AREAS, workflow_snapshot_digest
    project = Path(project).resolve()
    (project / 'md-drafts').mkdir(parents=True, exist_ok=True)
    targets = {'specification': ('spec', 'product_specification.md', 'product_specification.template.md'),
               'project_manual': ('manual', 'agent.md', 'project-manual.template.md'),
               'project_status': ('status', 'project_status.md', 'project_status.template.md'),
               'memory': ('memory', 'memory.md', 'memory.template.md'),
               'independent_review': ('review', 'REVIEW_REPORT.md', 'REVIEW_REPORT.template.md')}
    drafts, documents = [], []
    for role in ('specification', 'project_manual', 'project_status', 'memory', 'independent_review'):
        identifier, target, template = targets[role]
        sections = [{'id': key, 'heading': key.replace('_', ' ').title()} for key in ROLE_SECTIONS[role]]
        body = '# ' + ('Specification' if role == 'specification' else role.replace('_', ' ').title()) + '\n\n'
        body += 'Synthetic product behavior for fixture tests.\n\n'
        for section in sections:
            body += '## ' + section['heading'] + '\n\n'
            body += 'Fixture requirement REQ-1 and feature F1 have bounded acceptance.\n\n'
        if role == 'independent_review':
            body += 'Status: NOT_RUN\nReviewer: not assigned\n'
        raw = (DRAFT_MARKER + '\n' + body).encode('utf-8')
        draft = {'id': identifier, 'path': 'md-drafts/' + Path(target).stem + '.DRAFT.md',
                 'target': target, 'template': template,
                 'kind': 'specification' if role == 'specification' else 'document',
                 'required': True, 'sha256': sha256(raw), 'baseline_sha256': 'NOT_EXISTS',
                 'expected_sha256': '0' * 64, 'transforms': ['remove_draft_marker', 'normalize_utf8_lf']}
        output = expected_content(draft, raw)
        draft['expected_sha256'] = sha256(output)
        (project / draft['path']).write_bytes(raw)
        if complete:
            (project / target).write_bytes(output)
        drafts.append(draft)
        documents.append({'role': role, 'draft_id': identifier, 'sections': sections})
    packet = {'schema_version': '2.0', 'plan_id': 'test-plan', 'revision': '1', 'host': host,
              'project': {'name': 'Synthetic'}, 'route': 'new', 'scale': 'M', 'drafts': drafts}
    for key in ('facts', 'unknowns', 'conflicts', 'pains', 'roles', 'oss', 'folder_changes', 'risks',
                'code_map', 'timeline', 'approval_requests'):
        packet[key] = []
    packet['requirements'] = [{'id': 'REQ-1', 'text': 'Provide the synthetic fixture behavior.',
        'acceptance': ['The bounded fixture result is inspectable.'], 'source_ids': ['user-goal']}]
    packet['sources'] = [{'id': 'user-goal', 'kind': 'tool', 'required': True, 'depth': 'full',
                          'reference': 'synthetic-fixture:explicit-user-goal', 'verified': True}]
    packet['tools'] = [{'id': kind.lower(), 'kind': kind, 'decision': 'N/A',
                        'reason': 'Synthetic document-only fixture adopts no runtime tool.'}
                       for kind in ('SKILL', 'MCP', 'CLI', 'native_agent', 'Plugin')]
    if host == 'codex':
        packet['tools'].append({'id': 'gitnexus-project-onboarding', 'status': 'NOT_APPLICABLE',
            'skill_ref': 'synthetic-fixture:no-installed-skill-read',
            'reason': 'Document-only fixture: no Skill, Plugin or code adopted.',
            'artifacts': [], 'steps': [], 'acceptance': [], 'blockers': [], 'evidence': []})
    now = datetime.now(timezone.utc).isoformat(timespec='seconds')
    packet['workflow'] = {
        'roots': {'destination_mode': 'new_folder', 'docs_root': str(project), 'source_roots': [],
            'creation_receipt': {'plan_id': packet['plan_id'], 'path': str(project), 'before': 'NOT_EXISTS',
                'status': 'CREATED', 'observed_at': now, 'request_ref': 'synthetic-fixture:folder-request'}},
        'documents': documents,
        'phases': [{'id': i, 'status': 'COMPLETE' if i <= 4 or complete else 'PLANNED',
                    'required': i not in (6, 7), 'evidence': ['synthetic-fixture:phase'] if i <= 4 or complete else [],
                    'reason': 'Bounded fixture phase; no real execution implied.'} for i in range(10)],
        'discovery': {'status': 'NOT_APPLICABLE', 'reason': 'New synthetic project has no existing history.',
                      'inventory': [], 'queries': [], 'receipts': [], 'reads': [], 'limitations': []},
        'features': [{'id': 'F1', 'description': 'Synthetic fixture feature.', 'requirement_ids': ['REQ-1'],
                      'source_ids': ['user-goal'], 'acceptance': ['The bounded result exists.'],
                      'settings': [], 'settings_reason': 'No configurable setting in this fixture.'}],
        'decisions': {'events': [], 'current': []},
        'review': {'status': 'NOT_RUN', 'reviewer_id': '', 'author_id': 'fixture-author', 'revision': '1',
                   'snapshot_sha256': '', 'areas': [], 'changed_ids': [], 'affected_areas': []},
        'package': {'mode': 'none', 'status': 'NOT_APPLICABLE', 'root': '', 'reason': 'No plugin adopted.',
                    'inventory': [], 'fresh_session_evidence': []},
        'evidence_policy': {'authorized': False, 'approval_ref': '', 'paths': [], 'record_types': [], 'prefixes': []},
        'gitnexus': {'applicability': 'N/A' if host == 'zcode' else 'REQUIRED',
                     'tool_id': '' if host == 'zcode' else 'gitnexus-project-onboarding',
                     'reason': 'GitNexus is Codex-only; document fixture G6 uses its authoritative tool row.'},
        'issues': [],
        'effects': {'actions': [], 'git': {'status': 'NOT_APPLICABLE', 'reason': 'No git repo in synthetic fixture'}},
    }
    if complete:
        policy = packet['workflow']['evidence_policy']
        for role in ('project_status', 'memory'):
            target = targets[role][1]
            raw = (project / target).read_bytes()
            policy['prefixes'].append({'path': target, 'length': len(raw), 'sha256': sha256(raw)})
        review = packet['workflow']['review']
        review.update(status='ACCEPTED', reviewer_id='independent-fixture-reviewer',
                      snapshot_sha256=workflow_snapshot_digest(packet, project))
        areas = list(REVIEW_AREAS) + (['gitnexus'] if host == 'codex' else [])
        review['areas'] = [{'id': identifier, 'status': 'PASS', 'evidence': ['synthetic-fixture:review'],
                            'reason': 'Fixture-only evidence, not a real review.'} for identifier in areas]
        finalize_review_draft(packet, project, publish_fixture=True)
        record_fixture_promotion(packet, project)
    return packet


def finalize_review_draft(packet, project, publish_fixture=False):
    """Finalize actual fixture report within a not-yet-approved candidate revision."""
    from plan_contract import expected_content, sha256
    project = Path(project)
    doc = next(row for row in packet['workflow']['documents'] if row['role'] == 'independent_review')
    draft = next(row for row in packet['drafts'] if row['id'] == doc['draft_id'])
    path = project / draft['path']
    report = path.read_text(encoding='utf-8')
    report = report.replace('Status: NOT_RUN\nReviewer: not assigned\n', '')
    report += ('\nStatus: ' + packet['workflow']['review']['status'] + '\nReviewer: '
               + packet['workflow']['review']['reviewer_id'] + '\nSnapshot SHA-256: '
               + packet['workflow']['review']['snapshot_sha256'] + '\n')
    for area in packet['workflow']['review']['areas']:
        report += area['id'] + ': ' + area['status'] + ' — ' + area['reason'] + '\n'
    raw = report.encode('utf-8')
    path.write_bytes(raw)
    draft['sha256'] = sha256(raw)
    output = expected_content(draft, raw)
    draft['expected_sha256'] = sha256(output)
    if publish_fixture:
        (project / draft['target']).write_bytes(output)


def record_fixture_promotion(packet, project):
    """Create real NO_OP promotion evidence with an explicit synthetic decision.

    This uses the production pipeline in an owned fixture directory. It never
    fabricates a journal, reviewer or real user authorization.
    """
    from plan_contract import packet_digest
    from support import save_packet
    import plan_render
    import promote
    project = Path(project)
    save_packet(project, packet)
    plan_render.write_views(project, packet)
    approval = {'plan_id': packet['plan_id'], 'revision': packet['revision'],
                'packet_sha256': packet_digest(packet), 'approved_by': 'Synthetic fixture actual decision',
                'approved_at': datetime.now(timezone.utc).isoformat(), 'actions': []}
    for draft in packet['drafts']:
        approval['actions'].append({'draft_id': draft['id'], 'target': draft['target'],
            'draft_sha256': draft['sha256'], 'baseline_sha256': draft['baseline_sha256'],
            'expected_sha256': draft['expected_sha256'], 'transforms': draft['transforms'],
            'effects': ['write_file']})
    path = project / 'md-drafts/fixture-approval.json'
    path.write_text(json.dumps(approval, ensure_ascii=False), encoding='utf-8')
    result = promote.promote(project, path, apply=True)
    if result['status'] not in ('COMMITTED', 'NO_OP'):
        raise AssertionError('Synthetic actual fixture promotion did not commit: ' + str(result))
    return result
