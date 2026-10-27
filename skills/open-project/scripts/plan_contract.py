"""Shared schema, safe file access and content transforms for plan packets."""
from __future__ import annotations
import hashlib
import json
import math
import ntpath
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import stat

class PacketError(ValueError):
    pass

DRAFT_MARKER = '<!-- open-project:draft -->'
ARRAY_FIELDS = ('requirements','sources','facts','unknowns','conflicts','pains','roles','tools','oss','risks','folder_changes','drafts')
REQUIRED_FIELDS = ('schema_version','plan_id','revision','host','project','route','scale') + ARRAY_FIELDS
OPTIONAL_FIELDS = ('graph','code_map','timeline','execution','approval_requests','coverage','suggestions')
DRAFT_FIELDS = ('id','path','target','template','kind','required','sha256','baseline_sha256','expected_sha256','transforms')
KINDS = ('document','specification','zcode-agent','codex-agent')
TRANSFORMS = ('remove_draft_marker','normalize_utf8_lf')
HEX = re.compile(r'^[a-f0-9]{64}$')

def sha256(raw):
    return hashlib.sha256(raw).hexdigest()

def _json_value(value, where='plan'):
    if isinstance(value,str):
        if any(0xD800 <= ord(c) <= 0xDFFF for c in value):
            raise PacketError('invalid Unicode scalar in packet')
        return
    if value is None or isinstance(value, (bool, int)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise PacketError(where + ': non-finite number')
        return
    if isinstance(value, list):
        for item in value:
            _json_value(item, where)
        return
    if isinstance(value, dict) and all(isinstance(k,str) for k in value):
        for key, item in value.items():
            _json_value(key,where)
            _json_value(item, where)
        return
    raise PacketError(where + ': unsupported JSON value type')

def _text(value, where):
    if not isinstance(value,str) or not value.strip():
        raise PacketError(where + ': expected non-empty string')

def _keys(value, required, optional, where):
    if not isinstance(value,dict):
        raise PacketError(where + ': expected object')
    if set(required) - set(value):
        raise PacketError(where + ': missing fields: ' + ', '.join(sorted(set(required)-set(value))))
    if set(value)-set(required)-set(optional):
        raise PacketError(where + ': unsupported fields')

def _relative(rel, where='path'):
    _text(rel, where)
    if '\x00' in rel or '\\' in rel:
        raise PacketError(where + ': unsafe path')
    parts = rel.split('/')
    if PurePosixPath(rel).is_absolute() or PureWindowsPath(rel).drive or any(p in ('','.','..') for p in parts):
        raise PacketError(where + ': absolute or traversal path forbidden')
    reserved = re.compile(r'^(CON|PRN|AUX|NUL|CONIN\$|CONOUT\$|COM[1-9¹²³]|LPT[1-9¹²³])(?:\.|$)',re.I)
    if any(p.endswith((' ','.')) or reserved.match(p) or (getattr(ntpath,'isreserved',lambda value:False)(p)) or re.search(r'[<>:"|?*\x00-\x1f]',p) for p in parts):
        raise PacketError(where + ': unsafe path component')
    return parts

def resolve_inside(root, rel):
    parts = _relative(rel)
    root = Path(os.path.abspath(os.fspath(root)))
    chain = list(reversed(root.parents)) + [root]
    current = root
    for part in parts:
        current = current / part
        chain.append(current)
    for path in chain:
        try:
            info = path.lstat()
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise PacketError('cannot inspect project path') from exc
        if stat.S_ISLNK(info.st_mode) or getattr(info,'st_file_attributes',0) & 0x400:
            raise PacketError('symlink/junction/reparse path forbidden: ' + str(path))
    resolved = current.resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise PacketError('path escapes project') from exc
    return resolved

def _hash(value, where, baseline=False):
    if baseline and value == 'NOT_EXISTS':
        return
    if not isinstance(value,str) or not HEX.fullmatch(value):
        raise PacketError(where + ': expected lowercase SHA-256 digest')

def packet_digest(plan):
    _json_value(plan)
    return sha256(json.dumps(plan,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8'))

def read_draft(project, draft):
    try:
        raw = resolve_inside(project,draft['path']).read_bytes()
    except OSError as exc:
        raise PacketError('cannot read draft: ' + draft['path']) from exc
    if sha256(raw) != draft['sha256']:
        raise PacketError('draft hash mismatch: ' + draft['path'])
    try:
        raw.decode('utf-8')
    except UnicodeError as exc:
        raise PacketError('draft is not UTF-8: ' + draft['path']) from exc
    return raw

def expected_content(draft, raw):
    if not isinstance(raw,bytes):
        raise PacketError('expected_content requires bytes')
    output = raw
    for transform in draft['transforms']:
        if transform == 'remove_draft_marker':
            for ending in (b'\r\n',b'\n',b'\r'):
                prefix = DRAFT_MARKER.encode('utf-8') + ending
                if output.startswith(prefix):
                    output = output[len(prefix):]
                    break
            else:
                if output == DRAFT_MARKER.encode('utf-8'):
                    output = b''
                else:
                    raise PacketError('remove_draft_marker requires the exact marker on line 1')
        elif transform == 'normalize_utf8_lf':
            try:
                output = output.decode('utf-8-sig').replace('\r\n','\n').replace('\r','\n').encode('utf-8')
            except UnicodeError as exc:
                raise PacketError('normalization requires UTF-8') from exc
        else:
            raise PacketError('unsupported transform')
    return output

def validate_plan(data):
    _json_value(data)
    _keys(data,REQUIRED_FIELDS,OPTIONAL_FIELDS,'plan')
    if data['schema_version'] != '1.0':
        raise PacketError('supported schema_version is 1.0')
    _text(data['plan_id'],'plan_id')
    revision = data['revision']
    if not isinstance(revision,str) or not re.fullmatch(r'[1-9][0-9]*',revision):
        raise PacketError('revision must be a positive integer string')
    if data['host'] not in ('zcode','codex'):
        raise PacketError('host must be zcode or codex')
    if not isinstance(data['project'],dict):
        raise PacketError('project must be object')
    _text(data['project'].get('name'),'project.name')
    if data['route'] not in ('new','reorg') or data['scale'] not in ('S','M','L'):
        raise PacketError('unsupported route or scale')
    for field in ARRAY_FIELDS:
        if not isinstance(data[field],list):
            raise PacketError(field + ': expected array')
        if field not in ('sources','drafts') and any(not isinstance(v,(str,dict)) for v in data[field]):
            raise PacketError(field + ': items must be strings or objects')
    source_ids = set()
    source_fields = ('kind','path','sha256','required','title','description','url','notes','status','depth','reference','locator','verified','content_sha256')
    for source in data['sources']:
        _keys(source,('id',),source_fields,'source')
        _text(source['id'],'source.id')
        if source['id'] in source_ids:
            raise PacketError('duplicate source id')
        source_ids.add(source['id'])
        kind = source.get('kind','file' if 'path' in source else 'unknown')
        if kind not in ('file','session','url','tool','unknown'):
            raise PacketError('unsupported source kind')
        if kind == 'file' or 'path' in source:
            if 'path' not in source or 'sha256' not in source:
                raise PacketError('file source requires path and sha256')
            _relative(source['path'],'source.path')
            _hash(source['sha256'],'source.sha256')
        for field in ('sha256','content_sha256'):
            if field in source:
                _hash(source[field],'source.'+field)
        for field in ('required','verified'):
            if field in source and type(source[field]) is not bool:
                raise PacketError('source.'+field+': expected boolean')
        for field in ('title','description','url','status','reference','locator'):
            if field in source and not isinstance(source[field],str):
                raise PacketError('source.'+field+': expected string')
        if 'depth' in source and not isinstance(source['depth'],(str,dict)):
            raise PacketError('source.depth: expected string or object')
    draft_ids, paths, targets = set(),set(),set()
    for draft in data['drafts']:
        _keys(draft,DRAFT_FIELDS,('depends_on',),'draft')
        for field,seen in (('id',draft_ids),('path',paths),('target',targets)):
            _text(draft[field],'draft.'+field)
            token = draft[field].casefold()
            if token in seen:
                raise PacketError('duplicate draft '+field)
            seen.add(token)
        for field in ('path','target','template'):
            _relative(draft[field],'draft.'+field)
        if not draft['path'].startswith('md-drafts/'):
            raise PacketError('draft.path must be beneath md-drafts/')
        if draft['path'].casefold() in ('md-drafts/plan-data.json','md-drafts/plan.draft.md','md-drafts/plan-report.draft.html'):
            raise PacketError('draft.path collides with generated packet artifacts')
        if draft['target'].split('/')[0].casefold() in ('md-drafts','.git','.open-project-promotion'):
            raise PacketError('draft.target is a reserved project control path')
        if draft['kind'] not in KINDS:
            raise PacketError('unsupported draft kind')
        if draft['kind'] == 'zcode-agent' and data['host'] != 'zcode':
            raise PacketError('zcode-agent requires zcode host')
        if draft['kind'] == 'codex-agent' and data['host'] != 'codex':
            raise PacketError('codex-agent requires codex host')
        if type(draft['required']) is not bool:
            raise PacketError('draft.required must be boolean')
        for field in ('sha256','expected_sha256','baseline_sha256'):
            _hash(draft[field],'draft.'+field,field=='baseline_sha256')
        transforms = draft['transforms']
        if not isinstance(transforms,list) or any(not isinstance(v,str) or v not in TRANSFORMS for v in transforms):
            raise PacketError('unsupported transforms')
        if len(set(transforms)) != len(transforms):
            raise PacketError('duplicate transforms')
        if draft['kind'].endswith('-agent') and 'remove_draft_marker' in transforms:
            raise PacketError('agent drafts require native line 1 and normalization only')
        deps = draft.get('depends_on',[])
        if not isinstance(deps,list) or any(not isinstance(v,str) or not v for v in deps):
            raise PacketError('depends_on must be an array of draft IDs')
        if len(set(deps)) != len(deps):
            raise PacketError('duplicate draft dependencies')
    if not any(d['required'] and d['kind']=='specification' and PurePosixPath(d['target']).name=='product_specification.md' for d in data['drafts']):
        raise PacketError('required product_specification.md specification is mandatory')
    target_list = sorted(targets)
    for index,target in enumerate(target_list):
        if any(other.startswith(target + '/') for other in target_list[index+1:]):
            raise PacketError('draft targets cannot be ancestors of other targets')
    by_id = {d['id']:d for d in data['drafts']}
    pending = {identifier:set(draft.get('depends_on',[])) for identifier,draft in by_id.items()}
    if any(dep not in by_id for deps in pending.values() for dep in deps):
        raise PacketError('unknown draft dependency')
    while pending:
        completed = {identifier for identifier,deps in pending.items() if not deps}
        if not completed:
            raise PacketError('draft dependency cycle')
        pending = {identifier:deps-completed for identifier,deps in pending.items() if identifier not in completed}

def _pairs(pairs):
    result = {}
    for key,value in pairs:
        if key in result:
            raise PacketError('duplicate JSON key')
        result[key] = value
    return result

def _constant(value):
    raise PacketError('non-finite JSON constant')

def load_plan(project):
    try:
        raw = resolve_inside(project,'md-drafts/plan-data.json').read_bytes()
        data = json.loads(raw.decode('utf-8'),object_pairs_hook=_pairs,parse_constant=_constant)
    except (OSError,UnicodeError,json.JSONDecodeError) as exc:
        raise PacketError('cannot read valid md-drafts/plan-data.json') from exc
    validate_plan(data)
    return data


def schema_document():
    """JSON Schema mirrors the structural validator; path/DAG rules are semantic."""
    text = {'type':'string','minLength':1,'pattern':r'\S'}
    digest = {'type':'string','pattern':'^[a-f0-9]{64}$'}
    path = {'type':'string','minLength':1,'description':'Safe relative POSIX path. plan_contract enforces no traversal, Windows devices/ADS, links or reparse components.'}
    properties = {'schema_version':{'const':'1.0'},'plan_id':text,
        'revision':{'type':'string','pattern':'^[1-9][0-9]*$'},
        'host':{'enum':['zcode','codex']},'project':{'type':'object','required':['name'],'properties':{'name':text}},
        'route':{'enum':['new','reorg']},'scale':{'enum':['S','M','L']}}
    for field in ARRAY_FIELDS:
        properties[field] = {'type':'array','items':{'anyOf':[{'type':'string'},{'type':'object'}]}}
    source_properties = {'id':text,'kind':{'enum':['file','session','url','tool','unknown']},'path':path,
        'sha256':digest,'content_sha256':digest,'required':{'type':'boolean'},'verified':{'type':'boolean'},
        'depth':{'anyOf':[{'type':'string'},{'type':'object'}]},'notes':{}}
    for field in ('title','description','url','status','reference','locator'):
        source_properties[field] = {'type':'string'}
    properties['sources'] = {'type':'array','items':{'type':'object','required':['id'],
        'properties':source_properties,'additionalProperties':False,
        'allOf':[{'if':{'anyOf':[{'required':['path']},{'required':['kind'],'properties':{'kind':{'const':'file'}}}]},
                  'then':{'required':['path','sha256']}}]}}
    draft_properties = {field:path for field in ('path','target','template')}
    draft_properties.update({'id':text,'kind':{'enum':list(KINDS)},'required':{'type':'boolean'},
        'sha256':digest,'baseline_sha256':{'anyOf':[digest,{'const':'NOT_EXISTS'}]},'expected_sha256':digest,
        'transforms':{'type':'array','uniqueItems':True,'items':{'enum':list(TRANSFORMS)}},
        'depends_on':{'type':'array','uniqueItems':True,'items':text}})
    properties['drafts'] = {'type':'array','items':{'type':'object','required':list(DRAFT_FIELDS),
        'properties':draft_properties,'additionalProperties':False,
        'allOf':[{'if':{'properties':{'kind':{'enum':['zcode-agent','codex-agent']}}},
                  'then':{'properties':{'transforms':{'not':{'contains':{'const':'remove_draft_marker'}}}}}}]},
        'contains':{'type':'object','required':['kind','required','target'],
            'properties':{'kind':{'const':'specification'},'required':{'const':True},
                          'target':{'type':'string','pattern':r'(^|/)product_specification\.md$'}}}}
    for field in OPTIONAL_FIELDS:
        properties[field] = {}
    return {'$schema':'https://json-schema.org/draft/2020-12/schema',
        '$id':'https://open-project.local/plan.schema.json','title':'open-project packet 1.0',
        'type':'object','required':list(REQUIRED_FIELDS),'properties':properties,'additionalProperties':False,
        '$comment':'Semantic validation in plan_contract additionally enforces finite JSON/valid Unicode, safe and reserved paths, unique IDs/paths/targets, no ancestor target collisions, known acyclic draft dependencies, host/kind agreement and normalization-only native agent transforms.'}
