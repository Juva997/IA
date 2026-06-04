from __future__ import annotations

import ast
import os
import re
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Tuple


DocstringNode = ast.Module | ast.AsyncFunctionDef | ast.FunctionDef | ast.ClassDef


@dataclass
class DocIssue:
    filename: Optional[str]
    node_type: str  # 'module' | 'class' | 'function'
    name: Optional[str]
    lineno: int
    end_lineno: Optional[int]
    message: str
    original: Optional[str]
    suggestion: Optional[str]


def _fix_summary_line(line: str) -> str:
    s = (line or "").strip()
    if not s:
        return "Short description."
    if s and s[0].islower():
        s = s[0].upper() + s[1:]
    if not s.endswith((".", "!", "?")):
        s = s + "."
    return s


def _extract_docstring_info(node: DocstringNode, source_lines: List[str]) -> Tuple[Optional[str], int, int, Optional[str]]:
    """Return (docstring, doc_start_lineno, doc_end_lineno, raw_docstring_text).

    If no docstring exists, returns (None, node.lineno, node.end_lineno, None).
    """
    doc = ast.get_docstring(node, clean=False)
    if getattr(node, "body", None):
        first = node.body[0]
        if isinstance(first, ast.Expr):
            first_value = first.value
        else:
            first_value = None
        if isinstance(first_value, ast.Constant) and isinstance(first_value.value, str):
            start = getattr(first, "lineno", 1)
            # Try to locate end of the docstring block by scanning for closing triple quotes
            if start - 1 < len(source_lines):
                start_line_text = source_lines[start - 1]
                m = re.search(r'([ruRU]{0,2})(?P<quote>"""|\'\'\')', start_line_text)
                if m:
                    quote = m.group("quote")
                    for i in range(start - 1, len(source_lines)):
                        if i != start - 1 and source_lines[i].rstrip().endswith(quote):
                            end = i + 1
                            raw = "\n".join(source_lines[start - 1:end])
                            return doc, start, end, raw
            raw_end = getattr(first, "end_lineno", None)
            end = raw_end if isinstance(raw_end, int) else start
            raw_text: Optional[str] = "\n".join(source_lines[start - 1:end]) if start - 1 < len(source_lines) else None
            return doc, start, end, raw_text
    lineno = getattr(node, "lineno", 1)
    end_lineno = getattr(node, "end_lineno", lineno)
    return None, lineno, end_lineno, None


def _make_suggestion_for_node(node: DocstringNode, doc: Optional[str]) -> str:
    raw_name = getattr(node, "name", None)
    name = raw_name if isinstance(raw_name, str) and raw_name else "module"
    if not doc:
        summary = f"Short description for {name}."
        return f'"""{summary}"""'
    lines = doc.splitlines()
    first = lines[0] if lines else ""
    fixed_first = _fix_summary_line(first)
    rest = "\n".join(lines[1:]) if len(lines) > 1 else ""
    if rest.strip():
        return '"""' + fixed_first + "\n\n" + rest + '"""'
    else:
        return f'"""{fixed_first}"""'


def find_doc_issues(
    path: Optional[str] = None,
    text: Optional[str] = None,
    path_or_text: Optional[str] = None,
) -> List[DocIssue]:
    """Analisa um arquivo Python (path) ou trecho de código e retorna DocIssues.

    Compatível com chamadas posicionais antigas (`find_doc_issues(s)`) e também
    com argumentos nomeados `text=` ou `path=` para maior clareza.
    """
    candidate = path_or_text if path_or_text is not None else (text if text is not None else path)
    if candidate is None:
        raise ValueError("no_input_for_find_doc_issues")

    filename: Optional[str]
    if isinstance(candidate, str) and os.path.isfile(candidate):
        filename = candidate
        with open(candidate, "r", encoding="utf-8") as f:
            source = f.read()
    else:
        filename = None
        source = candidate if isinstance(candidate, str) else str(candidate)

    source_lines = source.splitlines()
    try:
        module = ast.parse(source)
    except SyntaxError as exc:
        return [
            DocIssue(
                filename=filename,
                node_type="module",
                name=None,
                lineno=exc.lineno or 1,
                end_lineno=getattr(exc, "end_lineno", exc.lineno),
                message=f"SyntaxError: {exc.msg}",
                original=None,
                suggestion=None,
            )
        ]

    issues: List[DocIssue] = []

    # module docstring
    module_doc, m_start, m_end, m_raw = _extract_docstring_info(module, source_lines)
    if not module_doc:
        suggestion = _make_suggestion_for_node(module, None)
        issues.append(DocIssue(filename=filename, node_type="module", name=None, lineno=1, end_lineno=None, message="Missing module docstring", original=None, suggestion=suggestion))
    else:
        summary = module_doc.splitlines()[0] if module_doc else ""
        fixed = _fix_summary_line(summary)
        if fixed != summary:
            suggestion = _make_suggestion_for_node(module, module_doc)
            issues.append(DocIssue(filename=filename, node_type="module", name=None, lineno=m_start, end_lineno=m_end, message="Module docstring summary style", original=m_raw, suggestion=suggestion))

    # top-level defs
    for node in module.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            doc, start_line, end_line, raw = _extract_docstring_info(node, source_lines)
            node_type = "class" if isinstance(node, ast.ClassDef) else "function"
            name = getattr(node, "name", None)
            if not doc:
                suggestion = _make_suggestion_for_node(node, None)
                issues.append(DocIssue(filename=filename, node_type=node_type, name=name, lineno=getattr(node, "lineno", 1), end_lineno=getattr(node, "end_lineno", None), message=f"Missing {node_type} docstring", original=None, suggestion=suggestion))
            else:
                summary = doc.splitlines()[0] if doc else ""
                fixed = _fix_summary_line(summary)
                if fixed != summary:
                    issues.append(DocIssue(filename=filename, node_type=node_type, name=name, lineno=start_line, end_lineno=end_line, message=f"{node_type.title()} docstring summary style", original=raw, suggestion=_make_suggestion_for_node(node, doc)))

    return issues


def _guess_indentation(line: str) -> str:
    m = re.match(r"^(\s*)", line)
    return m.group(1) if m else ""


def _indent_docstring_lines(docstring: str, indent: str) -> List[str]:
    s = docstring.strip()
    if not (s.startswith('"""') or s.startswith("'''")):
        s = '"""' + s + '"""'
    inner = re.sub(r'^([ruRU]{0,2})("""|\'\'\')', '', s, count=1)
    inner = re.sub(r'("""|\'\'\')$', '', inner, count=1)
    inner = inner.strip('\n')
    if "\n" in inner:
        lines = [indent + '"""'] + [indent + line for line in inner.splitlines()] + [indent + '"""']
    else:
        lines = [indent + '"""' + inner + '"""']
    return lines


def generate_patch_for_issue(issue: DocIssue, source_lines: List[str]) -> Tuple[int, int, List[str]]:
    if issue.original:
        start = issue.lineno
        end = issue.end_lineno or issue.lineno
        indent = _guess_indentation(source_lines[start - 1]) if start - 1 < len(source_lines) else ""
        new_lines = _indent_docstring_lines(issue.suggestion or '""" """', indent)
        return start, end, new_lines
    else:
        if issue.node_type == "module":
            start = 1
            end = 0
            indent = ""
        else:
            start = issue.lineno
            end = issue.lineno
            if start < len(source_lines):
                indent = _guess_indentation(source_lines[start])
            else:
                indent = _guess_indentation(source_lines[start - 1]) if start - 1 < len(source_lines) else ""
            if indent == "":
                indent = "    "
        new_lines = _indent_docstring_lines(issue.suggestion or '""" """', indent)
        return start, end, new_lines


def issues_to_dicts(issues: List[DocIssue]) -> List[Dict[str, Any]]:
    return [asdict(i) for i in issues]


if __name__ == "__main__":
    import json
    import sys

    if len(sys.argv) < 2:
        print("usage: python -m actions.tools.doc_validator path/to/file.py")
        sys.exit(1)
    p = sys.argv[1]
    iss = find_doc_issues(p)
    print(json.dumps(issues_to_dicts(iss), indent=2, ensure_ascii=False))
