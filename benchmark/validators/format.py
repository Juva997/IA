import json

from benchmark.validators.common import output_text


def format_check(test, outputs):
    expected_format = test.get("format")
    if not expected_format:
        return 1.0

    checks = {
        "json": _is_json,
        "table": _is_table,
        "plain": _is_plain_text,
    }
    checker = checks.get(str(expected_format).lower())
    if checker is None:
        return 1.0

    valid = sum(1 for output in outputs if checker(output_text(output)))
    return valid / len(outputs) if outputs else 0.0


def _is_json(text):
    try:
        json.loads(text)
        return True
    except (TypeError, ValueError):
        return False


def _is_table(text):
    lines = [line.strip() for line in str(text).splitlines() if line.strip()]
    if len(lines) < 2:
        return False
    return all("|" in line for line in lines[:2])


def _is_plain_text(text):
    stripped = str(text).strip()
    if not stripped:
        return False
    return not _is_json(stripped)
