import json


def normalize_record(response):
    if isinstance(response, dict):
        output = response.get("output")
        error = response.get("error")
        if output is None and error is not None:
            output = error
        if output is None:
            output = json.dumps(response, ensure_ascii=False, sort_keys=True)

        record = {
            "status": str(response.get("status") or ("error" if error else "success")).lower(),
            "output": str(output),
            "error": None if error is None else str(error),
            "raw": response,
        }
        _copy_optional_metadata(response, record)
        return record

    return {
        "status": "success",
        "output": str(response),
        "error": None,
        "raw": response,
    }


def _copy_optional_metadata(response, record):
    for key in (
        "trace",
        "cost",
        "iterations",
        "attempts",
        "evaluation",
        "simulation",
        "critique",
        "verification",
    ):
        if key in response:
            record[key] = response[key]


def output_text(record):
    if isinstance(record, dict) and isinstance(record.get("steps"), list):
        if not record["steps"]:
            return ""
        return output_text(record["steps"][-1])

    if isinstance(record, dict):
        return str(record.get("output", ""))

    return str(record)


def evaluation_text(record):
    texts = [output_text(record)]

    if isinstance(record, dict):
        artifacts = record.get("workspace_artifacts") or {}
        for path, metadata in sorted(artifacts.items()):
            if path == "config.json" or not isinstance(metadata, dict):
                continue
            text = metadata.get("text")
            if text:
                texts.append(f"\n[artifact:{path}]\n{text}")

    return "\n".join(str(text) for text in texts if text is not None)


def normalized_text(record):
    return " ".join(output_text(record).strip().lower().split())
