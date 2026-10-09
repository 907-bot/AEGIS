"""
TOON Codec — Token-Oriented Object Notation encoder/decoder for AEGIS.

Implements a subset of the TOON v3.3 spec (https://github.com/toon-format/spec)
sufficient for agent ↔ LLM structured-data exchange.

Key features used:
  - Objects:      key: value  (indentation-based nesting)
  - Primitive arrays inline:  tags[3]: admin,ops,dev
  - Tabular arrays:  items[2]{id,qty}: 1,5 \\n 2,3
  - Quoting rules per §7.2

This module provides:
  - encode(obj)   → TOON string
  - decode(text)  → Python dict / list
  - extract_toon(text) → safely pull a TOON block from LLM output
"""
from __future__ import annotations

import re
from typing import Any, Optional

# ──────────────────────────────────────────────────────────────
#  ENCODER  (dict/list → TOON text)
# ──────────────────────────────────────────────────────────────

_NEEDS_QUOTE_RE = re.compile(
    r'^$'                          # empty string
    r'|^\s|\s$'                    # leading/trailing whitespace
    r'|^(true|false|null)$'        # boolean/null literals
    r'|^-?\d+(?:\.\d+)?(?:e[+-]?\d+)?$'  # numeric-like
    r'|[:\"\\\[\]{},]'            # structural chars + comma delimiter
    r'|[\x00-\x1f]'               # control chars
    r'|^-',                         # starts with hyphen
    re.IGNORECASE,
)

_ESCAPE_MAP = {
    '\\': '\\\\',
    '"':  '\\"',
    '\n': '\\n',
    '\r': '\\r',
    '\t': '\\t',
}


def _escape(s: str) -> str:
    """Escape a string per TOON §7.1."""
    out: list[str] = []
    for ch in s:
        if ch in _ESCAPE_MAP:
            out.append(_ESCAPE_MAP[ch])
        elif ord(ch) < 0x20:
            out.append(f'\\u{ord(ch):04x}')
        else:
            out.append(ch)
    return ''.join(out)


def _encode_value(val: Any) -> str:
    """Encode a single primitive value."""
    if val is None:
        return 'null'
    if isinstance(val, bool):
        return 'true' if val else 'false'
    if isinstance(val, (int, float)):
        # Canonical number form per §2
        if isinstance(val, float):
            if val != val:       # NaN
                return 'null'
            if val == float('inf') or val == float('-inf'):
                return 'null'
            if val == 0.0:
                return '0'
            # Remove trailing zeros
            s = f'{val}'
            if '.' in s and 'e' not in s.lower():
                s = s.rstrip('0').rstrip('.')
            return s
        return str(val)
    s = str(val)
    if _NEEDS_QUOTE_RE.search(s):
        return f'"{_escape(s)}"'
    return s


def _is_tabular(arr: list) -> bool:
    """Check if array qualifies for TOON tabular form (§9.3)."""
    if not arr:
        return False
    if not all(isinstance(item, dict) for item in arr):
        return False
    if any(len(item) == 0 for item in arr):
        return False
    key_set = set(arr[0].keys())
    for item in arr[1:]:
        if set(item.keys()) != key_set:
            return False
    # All values must be primitives (no nested dicts/lists)
    for item in arr:
        for v in item.values():
            if isinstance(v, (dict, list)):
                return False
    return True


def _is_primitive_array(arr: list) -> bool:
    """Check if all items are primitives."""
    return all(not isinstance(v, (dict, list)) for v in arr)


def _encode_key(key: str) -> str:
    """Encode an object key per §7.3."""
    if re.match(r'^[A-Za-z_][A-Za-z0-9_.]*$', key):
        return key
    return f'"{_escape(key)}"'


def encode(obj: Any, indent_size: int = 2) -> str:
    """Encode a Python object to TOON format."""
    lines: list[str] = []
    _encode_node(obj, lines, depth=0, indent_size=indent_size)
    return '\n'.join(lines)


def _encode_node(obj: Any, lines: list[str], depth: int, indent_size: int,
                 key_prefix: Optional[str] = None):
    """Recursively encode a node into TOON lines."""
    indent = ' ' * (depth * indent_size)

    if isinstance(obj, dict):
        if key_prefix is not None:
            # This is a nested dict opened by "key:" on its own line
            pass  # parent already emitted "key:"
        for k, v in obj.items():
            ek = _encode_key(k)
            if isinstance(v, dict):
                if not v:
                    # Empty object
                    lines.append(f'{indent}{ek}:')
                else:
                    lines.append(f'{indent}{ek}:')
                    _encode_node(v, lines, depth + 1, indent_size)
            elif isinstance(v, list):
                _encode_array(ek, v, lines, depth, indent_size)
            else:
                lines.append(f'{indent}{ek}: {_encode_value(v)}')

    elif isinstance(obj, list):
        # Root-level array
        _encode_array(None, obj, lines, depth, indent_size)

    else:
        # Root primitive
        lines.append(f'{indent}{_encode_value(obj)}')


def _encode_array(key: Optional[str], arr: list, lines: list[str],
                  depth: int, indent_size: int):
    """Encode an array at the given depth."""
    indent = ' ' * (depth * indent_size)
    inner_indent = ' ' * ((depth + 1) * indent_size)
    n = len(arr)
    prefix = f'{key}' if key else ''

    if n == 0:
        # Empty array
        if key:
            lines.append(f'{indent}{key}: []')
        else:
            lines.append(f'{indent}[]')
        return

    if _is_primitive_array(arr):
        # Inline primitive array: key[N]: v1,v2,...
        vals = ','.join(_encode_value(v) for v in arr)
        lines.append(f'{indent}{prefix}[{n}]: {vals}')
        return

    if _is_tabular(arr):
        # Tabular form: key[N]{{f1,f2,...}}:
        fields = list(arr[0].keys())
        field_str = ','.join(_encode_key(f) for f in fields)
        lines.append(f'{indent}{prefix}[{n}]{{{field_str}}}:')
        for item in arr:
            row_vals = ','.join(_encode_value(item[f]) for f in fields)
            lines.append(f'{inner_indent}{row_vals}')
        return

    # Mixed / non-uniform expanded list
    lines.append(f'{indent}{prefix}[{n}]:')
    for item in arr:
        if isinstance(item, dict):
            if not item:
                lines.append(f'{inner_indent}-')
            else:
                first_key = True
                for k, v in item.items():
                    ek = _encode_key(k)
                    if first_key:
                        if isinstance(v, dict):
                            if not v:
                                lines.append(f'{inner_indent}- {ek}:')
                            else:
                                lines.append(f'{inner_indent}- {ek}:')
                                _encode_node(v, lines, depth + 2, indent_size)
                        elif isinstance(v, list):
                            # First field is array — handle inline
                            if _is_primitive_array(v) and v:
                                vals = ','.join(_encode_value(x) for x in v)
                                lines.append(f'{inner_indent}- {ek}[{len(v)}]: {vals}')
                            else:
                                _encode_array(f'- {ek}', v, lines, depth + 1, indent_size)
                        else:
                            lines.append(f'{inner_indent}- {ek}: {_encode_value(v)}')
                        first_key = False
                    else:
                        deeper_indent = ' ' * ((depth + 2) * indent_size)
                        if isinstance(v, dict):
                            lines.append(f'{inner_indent}  {ek}:')
                            _encode_node(v, lines, depth + 2, indent_size)
                        elif isinstance(v, list):
                            _encode_array(ek, v, lines, depth + 1, indent_size)
                        else:
                            lines.append(f'{inner_indent}  {ek}: {_encode_value(v)}')
        elif isinstance(item, list):
            if _is_primitive_array(item) and item:
                vals = ','.join(_encode_value(x) for x in item)
                lines.append(f'{inner_indent}- [{len(item)}]: {vals}')
            else:
                lines.append(f'{inner_indent}- [{len(item)}]:')
                for sub in item:
                    _encode_node(sub, lines, depth + 2, indent_size)
        else:
            lines.append(f'{inner_indent}- {_encode_value(item)}')


# ──────────────────────────────────────────────────────────────
#  DECODER  (TOON text → dict/list)
# ──────────────────────────────────────────────────────────────

_HEADER_RE = re.compile(
    r'^(?P<key>[A-Za-z_][A-Za-z0-9_.]*|"(?:[^"\\]|\\.)*")?'
    r'\[(?P<len>\d+)(?P<delim>[|\t])?\]'
    r'(?:\{(?P<fields>[^}]+)\})?'
    r':(?:\s+(?P<inline>.*))?$'
)

_KV_RE = re.compile(
    r'^(?P<key>[A-Za-z_][A-Za-z0-9_.]*|"(?:[^"\\]|\\.)*")'
    r':\s*(?P<val>.*)$'
)


def _unescape(s: str) -> str:
    """Unescape a TOON quoted string (§7.1)."""
    out: list[str] = []
    i = 0
    while i < len(s):
        if s[i] == '\\' and i + 1 < len(s):
            nxt = s[i + 1]
            if nxt == '\\':
                out.append('\\')
            elif nxt == '"':
                out.append('"')
            elif nxt == 'n':
                out.append('\n')
            elif nxt == 'r':
                out.append('\r')
            elif nxt == 't':
                out.append('\t')
            elif nxt == 'u' and i + 5 < len(s):
                hex_str = s[i+2:i+6]
                try:
                    out.append(chr(int(hex_str, 16)))
                except ValueError:
                    out.append(s[i:i+6])
                i += 4  # skip the 4 hex digits (the outer i+=2 handles \u)
            else:
                out.append(s[i:i+2])
            i += 2
        else:
            out.append(s[i])
            i += 1
    return ''.join(out)


def _unquote_key(k: str) -> str:
    """Unquote and unescape a key if quoted."""
    k = k.strip()
    if k.startswith('"') and k.endswith('"'):
        return _unescape(k[1:-1])
    return k


def _parse_value(token: str) -> Any:
    """Parse a primitive value token per §4."""
    token = token.strip()
    if not token:
        return ''
    if token == 'null':
        return None
    if token == 'true':
        return True
    if token == 'false':
        return False
    if token == '[]':
        return []
    # Quoted string
    if token.startswith('"') and token.endswith('"'):
        return _unescape(token[1:-1])
    # Try number
    try:
        if '.' in token or 'e' in token.lower():
            return float(token)
        return int(token)
    except ValueError:
        pass
    return token  # unquoted string


def _split_delimited(line: str, delim: str = ',') -> list[str]:
    """Split a delimited line respecting quotes."""
    parts: list[str] = []
    current: list[str] = []
    in_quote = False
    i = 0
    while i < len(line):
        ch = line[i]
        if ch == '"' and not in_quote:
            in_quote = True
            current.append(ch)
        elif ch == '"' and in_quote:
            # Check for escape
            if i > 0 and line[i-1] == '\\':
                current.append(ch)
            else:
                in_quote = False
                current.append(ch)
        elif ch == delim and not in_quote:
            parts.append(''.join(current).strip())
            current = []
        else:
            current.append(ch)
        i += 1
    parts.append(''.join(current).strip())
    return parts


def decode(text: str, indent_size: int = 2) -> Any:
    """Decode TOON text to a Python object."""
    lines = text.split('\n')
    # Remove trailing empty lines
    while lines and not lines[-1].strip():
        lines.pop()

    if not lines:
        return {}

    # Check for root array
    first_content = lines[0].strip()
    if first_content == '[]':
        return []

    first_match = _HEADER_RE.match(first_content)
    if first_match and not first_match.group('key'):
        # Root array
        return _decode_array(lines, 0, len(lines), indent_size, first_match)

    # Decode as object
    result = {}
    _decode_object(lines, 0, len(lines), 0, indent_size, result)
    return result


def _get_depth(line: str, indent_size: int) -> int:
    """Get indentation depth of a line."""
    spaces = len(line) - len(line.lstrip(' '))
    return spaces // indent_size


def _decode_object(lines: list[str], start: int, end: int,
                   expected_depth: int, indent_size: int, result: dict):
    """Decode object fields from lines[start:end] at expected_depth."""
    i = start
    while i < end:
        line = lines[i]
        stripped = line.strip()
        if not stripped:
            i += 1
            continue

        depth = _get_depth(line, indent_size)
        if depth < expected_depth:
            break
        if depth > expected_depth:
            i += 1
            continue

        # Check for array header
        header_match = _HEADER_RE.match(stripped)
        if header_match and header_match.group('key'):
            key = _unquote_key(header_match.group('key'))
            # Find scope end
            scope_end = _find_scope_end(lines, i + 1, end, expected_depth, indent_size)
            result[key] = _decode_array(
                lines, i, scope_end, indent_size, header_match
            )
            i = scope_end
            continue

        # Check for key: value
        kv_match = _KV_RE.match(stripped)
        if kv_match:
            key = _unquote_key(kv_match.group('key'))
            val_str = kv_match.group('val').strip()

            if not val_str:
                # Could be nested object
                scope_end = _find_scope_end(lines, i + 1, end, expected_depth, indent_size)
                nested = {}
                _decode_object(lines, i + 1, scope_end, expected_depth + 1, indent_size, nested)
                result[key] = nested
                i = scope_end
            elif val_str == '[]':
                result[key] = []
                i += 1
            else:
                # Check if this is an array header inline
                inline_header = _HEADER_RE.match(f'{key}{val_str}' if not val_str.startswith('[') else f'{key}{val_str}')
                result[key] = _parse_value(val_str)
                i += 1
        else:
            i += 1


def _decode_array(lines: list[str], header_line: int, scope_end: int,
                  indent_size: int, header_match: re.Match) -> list:
    """Decode an array from its header + body lines."""
    n = int(header_match.group('len'))
    delim = header_match.group('delim') or ','
    fields_str = header_match.group('fields')
    inline = header_match.group('inline')

    if n == 0:
        return []

    fields = None
    if fields_str:
        fields = [_unquote_key(f) for f in _split_delimited(fields_str, delim)]

    if inline and inline.strip():
        # Inline primitive array
        parts = _split_delimited(inline.strip(), delim)
        return [_parse_value(p) for p in parts]

    # Multi-line array
    result: list = []
    header_depth = _get_depth(lines[header_line], indent_size)
    item_depth = header_depth + 1
    i = header_line + 1

    if fields:
        # Tabular rows
        while i < scope_end:
            stripped = lines[i].strip()
            if not stripped:
                i += 1
                continue
            depth = _get_depth(lines[i], indent_size)
            if depth <= header_depth:
                break
            parts = _split_delimited(stripped, delim)
            row = {}
            for fi, field in enumerate(fields):
                row[field] = _parse_value(parts[fi]) if fi < len(parts) else None
            result.append(row)
            i += 1
    else:
        # Expanded list items
        while i < scope_end:
            stripped = lines[i].strip()
            if not stripped:
                i += 1
                continue
            depth = _get_depth(lines[i], indent_size)
            if depth <= header_depth:
                break
            if stripped.startswith('- '):
                item_content = stripped[2:]
                # Check for nested header
                nested_header = _HEADER_RE.match(item_content)
                if nested_header:
                    scope = _find_scope_end(lines, i + 1, scope_end, depth, indent_size)
                    result.append(_decode_array(lines, i, scope, indent_size, nested_header))
                    i = scope
                else:
                    result.append(_parse_value(item_content))
                    i += 1
            elif stripped == '-':
                result.append({})
                i += 1
            else:
                i += 1

    return result


def _find_scope_end(lines: list[str], start: int, end: int,
                    parent_depth: int, indent_size: int) -> int:
    """Find the end index of a nested scope."""
    i = start
    while i < end:
        stripped = lines[i].strip()
        if not stripped:
            i += 1
            continue
        depth = _get_depth(lines[i], indent_size)
        if depth <= parent_depth:
            return i
        i += 1
    return end


# ──────────────────────────────────────────────────────────────
#  EXTRACT — Pull TOON from LLM output (may be wrapped in markdown etc.)
# ──────────────────────────────────────────────────────────────

def extract_toon(text: str) -> dict:
    """
    Safely extract structured data from LLM output.

    Tries in order:
    1. Parse the whole text as TOON
    2. Find a ```toon ... ``` fenced block
    3. Find a ```...``` fenced block (generic)
    4. Find TOON-like content (key: value lines)
    5. Fall back to trying JSON extraction
    """
    import json
    import textwrap

    text = textwrap.dedent(text).strip()

    # 1. Try direct TOON parse
    try:
        result = decode(text)
        if isinstance(result, dict) and result:
            return result
    except Exception:
        pass

    # 2. Try fenced ```toon block
    toon_block = re.search(r'```toon\s*\n(.*?)```', text, re.DOTALL)
    if toon_block:
        try:
            result = decode(toon_block.group(1))
            if isinstance(result, dict) and result:
                return result
        except Exception:
            pass

    # 3. Try generic fenced block
    generic_block = re.search(r'```\s*\n(.*?)```', text, re.DOTALL)
    if generic_block:
        try:
            result = decode(generic_block.group(1))
            if isinstance(result, dict) and result:
                return result
        except Exception:
            pass

    # 4. Try to find TOON-like content (consecutive key: value lines)
    toon_lines: list[str] = []
    in_toon = False
    for line in text.split('\n'):
        stripped = line.strip()
        if _KV_RE.match(stripped) or _HEADER_RE.match(stripped):
            in_toon = True
            toon_lines.append(line)
        elif in_toon and (not stripped or line.startswith(' ')):
            toon_lines.append(line)
        elif in_toon and stripped:
            # Could be continuation or break
            if stripped.startswith('- '):
                toon_lines.append(line)
            else:
                break

    if toon_lines:
        try:
            result = decode('\n'.join(toon_lines))
            if isinstance(result, dict) and result:
                return result
        except Exception:
            pass

    # 5. Fallback: try JSON
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r'\{[\s\S]*\}', text)
        if match:
            try:
                return json.loads(match.group())
            except Exception:
                pass

    return {}


def dict_to_toon_prompt(schema: dict, indent: int = 0) -> str:
    """
    Convert a schema description dict into TOON-formatted prompt example.
    Used to instruct LLMs what TOON output to produce.
    """
    lines: list[str] = []
    prefix = '  ' * indent
    for key, val in schema.items():
        if isinstance(val, dict):
            lines.append(f'{prefix}{key}:')
            lines.append(dict_to_toon_prompt(val, indent + 1))
        elif isinstance(val, list):
            if val and isinstance(val[0], str):
                # Example list
                lines.append(f'{prefix}{key}[{len(val)}]: {",".join(val)}')
            else:
                lines.append(f'{prefix}{key}: []')
        else:
            lines.append(f'{prefix}{key}: {val}')
    return '\n'.join(lines)
