"""Read-only package inventory and local knowledge-link closure checks."""
from __future__ import annotations

from html import unescape
from html.parser import HTMLParser
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import posixpath
import re
import stat
from urllib.parse import unquote, urlsplit

from plan_contract import PacketError, resolve_inside, sha256


def _unsafe(info):
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, 'st_file_attributes', 0) & 0x400)


def _actual_files(root):
    """Inspect every directory entry without following links or reparse points."""
    root = Path(os.path.abspath(os.fspath(root)))
    for path in [*reversed(root.parents), root]:
        info = path.lstat()
        if _unsafe(info) or not stat.S_ISDIR(info.st_mode):
            raise PacketError('unsafe package directory: ' + str(path))
    files, pending = set(), [root]
    while pending:
        directory = pending.pop()
        if directory != root:
            resolve_inside(root, directory.relative_to(root).as_posix())
        info = directory.lstat()
        if _unsafe(info) or not stat.S_ISDIR(info.st_mode):
            raise PacketError('unsafe package directory before traversal: ' + str(directory))
        with os.scandir(directory) as entries:
            for entry in sorted(entries, key=lambda item: item.name):
                info = entry.stat(follow_symlinks=False)
                path = Path(entry.path)
                if _unsafe(info):
                    raise PacketError('package symlink/junction/reparse entry forbidden: ' + str(path))
                if stat.S_ISDIR(info.st_mode):
                    pending.append(path)
                elif stat.S_ISREG(info.st_mode):
                    files.add(path.relative_to(root).as_posix())
                else:
                    raise PacketError('package contains a non-regular file: ' + str(path))
    return files


def _without_code(text):
    output, fence = [], None
    for line in text.splitlines(keepends=True):
        marker = re.match(r'^ {0,3}(`{3,}|~{3,})', line)
        if fence:
            if marker and marker[1][0] == fence[0] and len(marker[1]) >= len(fence):
                fence = None
            output.append('\n')
        elif marker:
            fence = marker[1]
            output.append('\n')
        else:
            output.append(line)
    return re.sub(r'(`+).*?\1', '', ''.join(output), flags=re.S)


def _destination(text):
    """Extract one CommonMark-style destination; titles are not paths."""
    text = text.lstrip()
    if text.startswith('<'):
        end = text.find('>')
        if end < 0:
            raise PacketError('unterminated Markdown angle destination')
        return text[1:end]
    depth, out, escaped = 0, [], False
    for char in text:
        if escaped:
            if char not in r'''!"#$%&'()*+,-./:;<=>?@[\]^_`{|}~''':
                out.append('\\')
            out.append(char)
            escaped = False
            continue
        if char == '\\':
            escaped = True
            # Keep a backslash before non-punctuation so Windows/UNC paths are
            # rejected later rather than silently changing their meaning.
            continue
        if char.isspace() and depth == 0:
            break
        if char == ')':
            if depth == 0:
                break
            depth -= 1
        elif char == '(':
            depth += 1
        out.append(char)
    if escaped:
        out.append('\\')
    return ''.join(out)


class _HTMLLinks(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.targets = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        key = 'href' if tag == 'a' else 'src' if tag == 'img' else None
        if key and key in attrs and attrs[key] is not None:
            self.targets.append(attrs[key])


def _labels(text):
    """Yield balanced Markdown labels, including nested link/image text."""
    cursor = 0
    while cursor < len(text):
        if text[cursor] == '\\':
            cursor += 2
            continue
        if text[cursor] != '[':
            cursor += 1
            continue
        start, end, depth = cursor + 1, cursor + 1, 1
        while end < len(text) and depth:
            if text[end] == '\\':
                end += 2
                continue
            depth += (text[end] == '[') - (text[end] == ']')
            end += 1
        if depth:
            cursor += 1
            continue
        yield text[start:end - 1], end
        cursor = end


def _markdown_targets(text):
    text = _without_code(text)
    targets, definitions = [], {}
    for match in re.finditer(r'^ {0,3}\[([^\]\n]+)\]:[ \t]*(.*)$', text, re.M):
        destination = _destination(match[2])
        definitions[re.sub(r'\s+', ' ', match[1]).strip().casefold()] = destination
        targets.append(destination)
    for label, end in _labels(text):
        tail = text[end:]
        if tail.startswith('('):
            targets.append(_destination(tail[1:]))
        elif tail.startswith('['):
            reference = re.match(r'^\[([^\]\n]*)\]', tail)
            if reference:
                identifier = re.sub(r'\s+', ' ', reference[1] or label).strip().casefold()
                if identifier not in definitions:
                    raise PacketError('unresolved Markdown reference: ' + identifier)
                targets.append(definitions[identifier])
        elif not tail.startswith(':'):
            identifier = re.sub(r'\s+', ' ', label).strip().casefold()
            if identifier in definitions:
                targets.append(definitions[identifier])
    parser = _HTMLLinks()
    parser.feed(text)
    targets.extend(parser.targets)
    return targets


def _local_target(root, document, target, included):
    target = unescape(target.strip())
    if '\\' in target or target.startswith('//'):
        raise PacketError('absolute/UNC/backslash knowledge link forbidden: ' + target)
    try:
        parsed = urlsplit(target)
        if parsed.scheme in ('http', 'https') and parsed.netloc and parsed.hostname:
            return  # External citations are not fetched or counted as local files.
        if parsed.scheme or parsed.netloc:
            raise PacketError('unsupported or local absolute knowledge link: ' + target)
        path = unquote(parsed.path, errors='strict')
    except (ValueError, UnicodeError) as exc:
        raise PacketError('invalid knowledge-link URL: ' + target) from exc
    if not path:
        return  # Current-document fragment/query; heading validity is not inferred.
    if '\\' in path or PurePosixPath(path).is_absolute() or PureWindowsPath(path).drive:
        raise PacketError('absolute knowledge path forbidden: ' + target)
    relative = posixpath.normpath(posixpath.join(posixpath.dirname(document), path))
    if relative == '..' or relative.startswith('../'):
        raise PacketError('knowledge link escapes package: ' + target)
    if relative in ('', '.'):
        return
    destination = resolve_inside(root, relative)
    if relative in included and destination.is_file():
        return
    if destination.is_dir() and any(item.startswith(relative + '/') for item in included):
        return
    raise PacketError('unresolved or unlisted knowledge link: ' + target)


def package_findings(plan, project, stage='plan'):
    """Return standardized errors; never build, install, fetch or modify a file."""
    findings = []
    def fail(code, message):
        findings.append({'severity': 'error', 'code': code, 'message': message})
    if stage not in ('plan', 'completion'):
        fail('W_PACKAGE_STAGE', 'unknown package validation stage')
        return findings
    package = plan.get('workflow', {}).get('package', {})
    if package.get('mode') == 'none' or stage != 'completion':
        return findings
    root = package.get('root', '')
    if not root or not Path(root).is_absolute():
        fail('W_PACKAGE_PATH', 'completed package requires an absolute package root')
        return findings
    items = package.get('inventory', [])
    included = {item['package_path'] for item in items if item['disposition'] == 'included'}
    try:
        actual = _actual_files(root)
    except (OSError, PacketError) as exc:
        fail('W_PACKAGE_PATH', str(exc))
        return findings
    for label, paths in [('missing', included - actual), ('extra', actual - included)]:
        if paths:
            fail('W_PACKAGE_FILES', label + ' package files: ' + ', '.join(sorted(paths)))
    if package.get('mode') == 'local_adapter':
        from workflow_contract import source_location
        for item in items:
            if item['disposition'] != 'external' or not item['required']:
                continue
            try:
                source = source_location(plan, project, {'root_id': item['source_root'], 'path': item['path']})
                if sha256(source.read_bytes()) != item['sha256']:
                    fail('W_PACKAGE_EXTERNAL', 'external dependency hash mismatch: ' + item['path'])
            except (OSError, PacketError) as exc:
                fail('W_PACKAGE_EXTERNAL', str(exc))
    if package.get('mode') == 'knowledge_bundle':
        for document in sorted(included & actual):
            if Path(document).suffix.casefold() not in ('.md', '.markdown'):
                continue
            try:
                text = resolve_inside(root, document).read_text(encoding='utf-8')
                for target in _markdown_targets(text):
                    _local_target(root, document, target, included)
            except (OSError, PacketError, UnicodeError) as exc:
                fail('W_PACKAGE_LINK', document + ': ' + str(exc))
    return findings
