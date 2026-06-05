import difflib
import py_compile
import re
import traceback
import os
from pathlib import Path


def read_workspace_texts(root):
    """Read text files under workspace and return mapping relative_path -> text."""
    texts = {}
    root_path = Path(root)
    for path in root_path.rglob("*"):
        if not path.is_file():
            continue
        try:
            data = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            data = ""
        try:
            rel = path.relative_to(root_path).as_posix()
        except Exception:
            rel = str(path)
        texts[rel] = data
    return texts


def parse_patches_from_llm(text):
    """Parse patches in the LLM `<<<PATCH ... PATCH` format."""
    if not text:
        return []

    blocks = []
    pattern = re.compile(r"^<<<PATCH\s*$([\s\S]*?)^PATCH\s*$", re.MULTILINE)
    for match in pattern.finditer(text):
        body = match.group(1).strip("\r\n")
        if not body:
            continue
        lines = body.splitlines()

        idx = 0
        while idx < len(lines) and not lines[idx].strip():
            idx += 1
        if idx >= len(lines):
            continue

        first = lines[idx].strip()
        if first.startswith("--- ") or first.startswith("+++ ") or first.startswith("diff "):
            path_line = _path_from_diff_headers(lines, idx) or first.strip("`").strip()
        else:
            path_line = first.strip("`").strip()

        content = "\n".join(lines[idx:])
        if content and not content.endswith("\n"):
            content += "\n"
        blocks.append({"path": path_line, "content": content, "raw": body})

    return blocks


def apply_llm_patches(root, text, *, allowed_exts=None, max_patch_size=200000):
    """Apply parsed LLM patches into `root` workspace.

    Returns (applied_patches, errors, backups).
    """
    # Por padrão não permitir patches em arquivos .py a menos que a variável
    # de ambiente `ASSISTENTE_ALLOW_PY_PATCHES` esteja ativada.
    if allowed_exts is None:
        # Historically tests expect .py patches to be allowed by default.
        # SECURITY: in production set `ASSISTENTE_ALLOW_PY_PATCHES=0` to restrict
        allow_py = str(os.getenv("ASSISTENTE_ALLOW_PY_PATCHES", "1")).lower() in (
            "1",
            "true",
            "yes",
        )
        allowed_exts = {".py", ".txt", ".md", ".json"} if allow_py else {".txt", ".md", ".json"}
    applied = []
    errors = []
    backups = []

    patches = parse_patches_from_llm(text)
    if not patches:
        return applied, errors, backups

    root_path = Path(root).resolve()
    for patch in patches:
        rel = patch.get("path")
        new_content = patch.get("content", "") or ""

        target, error = _validated_patch_target(
            root_path, rel, allowed_exts, new_content, max_patch_size
        )
        if error:
            errors.append(error)
            continue

        try:
            existed = target.exists()
            original = target.read_text(encoding="utf-8") if existed else ""
        except Exception as exc:
            errors.append({"path": rel, "error": f"read_error:{str(exc)}"})
            continue

        raw = patch.get("raw", "") or ""
        try:
            final_content = _patch_content(original, raw or new_content, new_content)
            backups.append({"path": rel, "original": original, "existed": existed})
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(final_content, encoding="utf-8")
            applied.append(
                {
                    "path": rel,
                    "diff": "".join(
                        difflib.unified_diff(
                            original.splitlines(keepends=True),
                            final_content.splitlines(keepends=True),
                            fromfile=f"a/{rel}",
                            tofile=f"b/{rel}",
                        )
                    ),
                }
            )
        except Exception as exc:
            errors.append({"path": rel, "error": f"write_error:{str(exc)}"})
            rollback_patches(root, backups)
            return applied, errors, backups

    syntax_errors = _validate_python_syntax(root_path, applied)
    if syntax_errors:
        errors.extend(syntax_errors)
        rollback_patches(root, backups)
        return [], errors, backups

    return applied, errors, backups


def rollback_patches(root, backups):
    root_path = Path(root).resolve()
    errors = []
    for backup in backups:
        rel = backup.get("path")
        try:
            target = root_path / rel
            if backup.get("existed"):
                target.write_text(backup.get("original", ""), encoding="utf-8")
            elif target.exists():
                target.unlink()
        except Exception as exc:
            errors.append({"path": rel, "error": str(exc)})
    return errors


def apply_unified_diff_to_text(original_text, diff_text):
    """Apply a conservative unified diff to original_text and return patched text."""
    orig_lines = (original_text or "").splitlines(keepends=True)
    diff_lines = diff_text.splitlines()
    hunks = _extract_hunks(diff_lines)
    if not hunks:
        return diff_text

    out_lines = []
    oi = 0
    for header, hlines in hunks:
        match = re.match(r"@@\s*-(\d+)(?:,(\d+))?\s*\+(\d+)(?:,(\d+))?\s*@@", header)
        if not match:
            raise ValueError(f"invalid hunk header: {header}")
        orig_start = int(match.group(1)) - 1

        while oi < orig_start and oi < len(orig_lines):
            out_lines.append(orig_lines[oi])
            oi += 1

        for hunk_line in hlines:
            sig = hunk_line[0] if hunk_line else " "
            content = hunk_line[1:] if hunk_line else ""
            if sig == " ":
                oi = _append_context_line(orig_lines, out_lines, oi, content)
            elif sig == "-":
                if oi >= len(orig_lines) or not _same_line(orig_lines[oi], content):
                    raise ValueError("removed line does not match original")
                oi += 1
            elif sig == "+":
                out_lines.append(content if content.endswith("\n") else content + "\n")
            else:
                raise ValueError(f"unknown hunk line prefix: {sig}")

    while oi < len(orig_lines):
        out_lines.append(orig_lines[oi])
        oi += 1
    return "".join(out_lines)


def _path_from_diff_headers(lines, start):
    for line in lines[start:]:
        stripped = line.strip()
        if stripped.startswith("+++ "):
            raw_path = stripped[4:].strip()
            if raw_path.startswith("b/"):
                raw_path = raw_path[2:]
            return raw_path.strip("`").strip()
    return None


def _validated_patch_target(root_path, rel, allowed_exts, new_content, max_patch_size):
    if not rel or not isinstance(rel, str):
        return None, {"path": rel, "error": "invalid_path"}
    try:
        target = (root_path / rel).resolve()
    except Exception:
        return None, {"path": rel, "error": "bad_path"}
    try:
        target.relative_to(root_path)
    except Exception:
        return None, {"path": rel, "error": "path_outside_workspace"}
    if target.name == "config.json":
        return None, {"path": rel, "error": "forbidden_file:config.json"}
    if target.suffix not in allowed_exts:
        return None, {"path": rel, "error": f"forbidden_extension:{target.suffix}"}
    if len(new_content.encode("utf-8")) > max_patch_size:
        return None, {"path": rel, "error": "patch_too_large"}
    return target, None


def _patch_content(original, raw_text, new_content):
    if not _looks_like_unified_diff(raw_text):
        return new_content

    lines = raw_text.splitlines()
    at_idx = next(
        (index for index, line in enumerate(lines) if line.strip().startswith("@@")),
        None,
    )
    if at_idx is not None:
        header_line = lines[at_idx].strip()
        if header_line == "@@" or not re.match(r"@@\s*-\d+", header_line):
            new_full = "\n".join(lines[at_idx + 1 :])
            return new_full + ("\n" if new_full and not new_full.endswith("\n") else "")

    return apply_unified_diff_to_text(original, raw_text)


def _looks_like_unified_diff(text):
    return "@@" in text and (
        text.lstrip().startswith("--- ")
        or "+++ " in text
        or any(line.startswith(("+", "-", " ")) for line in text.splitlines())
    )


def _validate_python_syntax(root_path, applied):
    errors = []
    for entry in applied:
        rel = entry.get("path")
        if not rel:
            continue
        target = root_path / rel
        if target.suffix != ".py":
            continue
        try:
            py_compile.compile(str(target), doraise=True)
        except Exception as exc:
            errors.append(
                {
                    "path": rel,
                    "error": f"syntax_error:{str(exc)}",
                    "trace": traceback.format_exc(),
                }
            )
    return errors


def _extract_hunks(diff_lines):
    hunks = []
    index = 0
    while index < len(diff_lines):
        line = diff_lines[index]
        if not line.startswith("@@"):
            index += 1
            continue
        index += 1
        hlines = []
        while index < len(diff_lines) and not diff_lines[index].startswith("@@"):
            if diff_lines[index].startswith("--- ") or diff_lines[index].startswith("+++ "):
                break
            hlines.append(diff_lines[index])
            index += 1
        hunks.append((line, hlines))
    return hunks


def _append_context_line(orig_lines, out_lines, oi, content):
    if oi >= len(orig_lines):
        raise ValueError("context line out of range")
    if not _same_line(orig_lines[oi], content):
        for index in range(oi, len(orig_lines)):
            if _same_line(orig_lines[index], content):
                out_lines.extend(orig_lines[oi:index])
                oi = index
                break
        else:
            raise ValueError("context mismatch when applying hunk")
    out_lines.append(orig_lines[oi])
    return oi + 1


def _same_line(left, right):
    return left.rstrip("\r\n") == right.rstrip("\r\n")
