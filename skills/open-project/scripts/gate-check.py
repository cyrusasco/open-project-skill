"""Read-only packet checks. Advisory reports never imply promotion approval."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path, PurePosixPath
import posixpath
import re
import sys
from urllib.parse import unquote, urlsplit
from plan_contract import PacketError, load_plan, validate_plan, resolve_inside, sha256, packet_digest, read_draft, expected_content


def _yaml_scalar(raw):
    """One-line YAML scalar subset; never consume a following key as a value."""
    value = raw.lstrip(' ')
    if not value or value.startswith('#'):
        return ''
    if value[0] == "'":
        result = ''
        index = 1
        while index < len(value):
            if value[index] == "'":
                if index + 1 < len(value) and value[index+1] == "'":
                    result += "'"
                    index += 2
                    continue
                trailing = value[index+1:].strip()
                if trailing and not trailing.startswith('#'):
                    raise PacketError('invalid YAML quoted scalar')
                return result
            result += value[index]
            index += 1
        raise PacketError('unterminated YAML scalar')
    if value[0] == '"':
        try:
            decoded, end = json.JSONDecoder().raw_decode(value)
        except ValueError as exc:
            raise PacketError('invalid YAML quoted scalar') from exc
        if not isinstance(decoded,str):
            raise PacketError('invalid YAML scalar type')
        trailing = value[end:].strip()
        if trailing and not trailing.startswith('#'):
            raise PacketError('invalid YAML scalar suffix')
        return decoded
    value = re.split(r'\s+#',value,maxsplit=1)[0].strip()
    if value in ('null','Null','NULL','~'):
        return ''
    if value.casefold() in ('true','false','yes','no','on','off','.inf','+.inf','-.inf','.nan') or re.fullmatch(r'[-+]?(?:[0-9][0-9_]*(?:\.[0-9_]*)?(?:[eE][-+]?[0-9]+)?|\.[0-9]+(?:[eE][-+]?[0-9]+)?|0[xob][0-9a-fA-F_]+)',value):
        raise PacketError('YAML model scalar must be literal text')
    if re.search(r':(?:\s|$)',value):
        raise PacketError('invalid YAML plain scalar')
    if value.startswith(('|','>','[','{','&','*','!')):
        raise PacketError('unsupported YAML scalar syntax')
    return value


def _agent_error(draft, raw):
    if draft['kind'] not in ('zcode-agent','codex-agent'):
        return None
    text = raw.decode('utf-8').replace('\r\n','\n').replace('\r','\n')
    if draft['kind'] == 'codex-agent':
        try:
            import tomllib
        except ImportError:
            return 'G3: native Codex TOML validation requires Python 3.11 or newer: ' + draft['path']
        try:
            values = tomllib.loads(text)
        except tomllib.TOMLDecodeError:
            return 'G3: codex-agent requires valid native TOML: ' + draft['path']
        for field in ('name','description','developer_instructions'):
            if not isinstance(values.get(field),str) or not values[field].strip():
                return 'G3: codex-agent requires non-empty ' + field + ': ' + draft['path']
        if 'model' in values and (not isinstance(values['model'],str) or not values['model'].strip()):
            return 'G3: codex-agent model must be non-empty text when supplied: ' + draft['path']
        return None
    if not text.startswith('---\n'):
        return 'G3: zcode-agent frontmatter must begin on line 1: ' + draft['path']
    lines = text.split('\n')
    try:
        end = lines.index('---',1)
    except ValueError:
        return 'G3: zcode-agent frontmatter is not closed: ' + draft['path']
    fields = {}
    try:
        for line in lines[1:end]:
            if not line.strip() or line.lstrip().startswith('#'):
                continue
            match = re.fullmatch(r'([A-Za-z_][A-Za-z0-9_-]*):[ \t]*(.*)',line)
            if not match:
                raise PacketError('unsupported YAML frontmatter line')
            key,value = match.groups()
            if key in fields:
                raise PacketError('duplicate YAML frontmatter key')
            # Other native fields such as tools arrays remain opaque.
            fields[key] = _yaml_scalar(value) if key in ('name','description','model') else value
    except PacketError:
        return 'G3: invalid one-line YAML scalar frontmatter: ' + draft['path']
    model = fields.get('model','').strip()
    if not model or model.casefold() == 'inherit' or '<' in model or '>' in model or re.search(r'placeholder|待確認|待填|待定',model,re.I):
        return 'G3: zcode-agent model must be an explicit literal; empty/inherit/placeholder forbidden: ' + draft['path']
    return None


def _markdown_refs(text):
    # Match link destinations and inline-code relative Markdown paths, including Unicode.
    text = re.sub(r'```.*?```','',text,flags=re.S)
    for match in re.finditer(r'!?\[[^\]\n]*\]\(\s*(<[^>\n]+>|[^)\s]+)(?:\s+[^)]*)?\)',text):
        yield match.group(1).strip('<>')
    for match in re.finditer(r'^\s*\[[^\]\n]+\]:\s*(<[^>\n]+>|\S+)',text,re.M):
        yield match.group(1).strip('<>')
    for match in re.finditer(r'`([^`\n]+\.md(?:#[^`\n]*)?)`',text):
        yield match.group(1)


def _reference_warnings(project, draft, raw, targets):
    warnings = []
    seen = set()
    for ref in _markdown_refs(raw.decode('utf-8')):
        try:
            parsed = urlsplit(ref)
        except ValueError:
            warnings.append('G5: malformed Markdown reference in ' + draft['target'])
            continue
        if parsed.scheme or parsed.netloc or not parsed.path or not parsed.path.lower().endswith('.md'):
            continue
        refpath = unquote(parsed.path)
        if refpath.startswith('/'):
            continue
        relative = posixpath.normpath(posixpath.join(posixpath.dirname(draft['target']),refpath))
        if relative in seen:
            continue
        seen.add(relative)
        if relative in targets:
            continue
        try:
            found = resolve_inside(project,relative).is_file()
        except PacketError:
            found = False
        if not found:
            warnings.append('G5: missing relative Markdown reference from ' + draft['target'] + ': ' + refpath)
    return warnings


def inspect_packet(project, plan=None):
    result = {'ready':False,'errors':[],'warnings':[],'packet_sha256':None,'host':None}
    errors,warnings = result['errors'],result['warnings']
    try:
        plan = load_plan(project) if plan is None else plan
        validate_plan(plan)
        result['packet_sha256'] = packet_digest(plan)
        result['host'] = plan['host']
    except (PacketError,OSError,ValueError,TypeError,KeyError) as exc:
        errors.append('G1: invalid packet: ' + str(exc))
        return result
    targets = {d['target']:d for d in plan['drafts']}
    target_locations = {}
    for draft in plan['drafts']:
        try:
            canonical = os.path.normcase(os.fspath(resolve_inside(project,draft['target'])))
            target_locations[canonical] = draft
        except PacketError:
            # Per-draft checks below report unsafe target paths.
            continue
    for source in plan['sources']:
        label = source['id']
        required = source.get('required',True)
        if source.get('kind') == 'file' or 'path' in source:
            try:
                location = resolve_inside(project,source['path'])
                digest = sha256(location.read_bytes())
                if digest != source['sha256']:
                    draft = target_locations.get(os.path.normcase(os.fspath(location)))
                    if draft and source['sha256'] == draft['baseline_sha256'] and digest == draft['expected_sha256']:
                        warnings.append('G1: source is recorded pre-promotion evidence for expected target: ' + source['path'])
                    else:
                        raise PacketError('source hash mismatch: ' + source['path'])
            except (PacketError,OSError) as exc:
                (errors if required else warnings).append('G1: ' + (str(exc) if isinstance(exc,PacketError) else 'cannot read source: ' + source['path']))
        else:
            verified = source.get('verified') is True
            captured = any(isinstance(source.get(k),str) and source[k].strip() for k in ('url','reference','locator'))
            if source.get('kind','unknown') == 'unknown' or not verified or not captured:
                (errors if required else warnings).append('G1: external source requires explicit verified captured reference: ' + label)
    for draft in plan['drafts']:
        try:
            resolve_inside(project,draft['target'])
            raw = read_draft(project,draft)
            expected = expected_content(draft,raw)
            body = expected.decode('utf-8-sig')
            if body.startswith('<!-- open-project:draft -->'):
                body = body[len('<!-- open-project:draft -->'):]
            if draft['required'] and not body.strip():
                raise PacketError('required draft has no content: ' + draft['path'])
            if 'remove_draft_marker' in draft['transforms'] and b'<!-- open-project:draft -->' in raw and not (raw == b'<!-- open-project:draft -->' or raw.startswith((b'<!-- open-project:draft -->\n',b'<!-- open-project:draft -->\r'))):
                raise PacketError('draft marker must be the exact first line when present: ' + draft['path'])
            if sha256(expected) != draft['expected_sha256']:
                raise PacketError('expected content hash mismatch: ' + draft['path'])
            agent_error = _agent_error(draft,raw)
            if agent_error:
                errors.append(agent_error)
            warnings.extend(_reference_warnings(project,draft,raw,targets))
        except (PacketError,OSError,UnicodeError) as exc:
            (errors if draft['required'] else warnings).append('G1: ' + (str(exc) if isinstance(exc,PacketError) else 'cannot inspect draft: ' + draft['path']))
    # All views must be complete canonical derivations; mtime is not evidence of parity.
    try:
        from plan_render import render_views
        expected_md,expected_html = render_views(project,plan)
        for path,text in (('md-drafts/PLAN.DRAFT.md',expected_md),('md-drafts/PLAN-REPORT.DRAFT.html',expected_html)):
            location = resolve_inside(project,path)
            try:
                actual = location.read_bytes()
            except OSError:
                errors.append('G2: missing generated view: ' + path)
                continue
            if actual != text.encode('utf-8'):
                errors.append('G2: generated view differs from canonical packet: ' + path)
    except (PacketError,OSError,ValueError,TypeError,KeyError) as exc:
        errors.append('G2: cannot verify canonical views: ' + str(exc))
    result['ready'] = not errors
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description='Read-only plan packet gate (advisory by default)')
    parser.add_argument('project',type=Path)
    parser.add_argument('--strict',action='store_true')
    parser.add_argument('--json',action='store_true',dest='as_json')
    parser.add_argument('--out',type=Path,help='Optional report path explicitly selected by the caller')
    args = parser.parse_args(argv)
    result = inspect_packet(args.project)
    if args.as_json:
        output = json.dumps(result,ensure_ascii=False,sort_keys=True) + '\n'
    else:
        lines = ['READY' if result['ready'] else 'NOT_READY']
        lines += ['[FAIL] ' + error for error in result['errors']]
        lines += ['[WARN] ' + warning for warning in result['warnings']]
        lines += ['Advisory mode reports readiness; it does not authorize promotion.']
        output = '\n'.join(lines) + '\n'
    if args.out:
        args.out.write_text(output,encoding='utf-8',newline='\n')
    print(output,end='')
    return 1 if args.strict and not result['ready'] else 0

if __name__ == '__main__':
    raise SystemExit(main())
