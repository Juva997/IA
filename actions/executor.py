import traceback


class Executor:
    def __init__(self, registry, max_retries=2):
        self.registry = registry
        self.max_retries = max_retries

    # =========================
    def execute(self, decision, state):
        if not self._is_valid_decision(decision):
            return self._error("invalid_decision_format")

        action = decision.get("action")
        action_type = decision.get("type", "tool")
        data = self._sanitize_data(action, decision.get("data"))

        if data is None:
            return self._error("invalid_data_after_sanitize")

        if action_type == "specialist":
            return self._execute_specialist(action, state)

        tool = self.registry.get(action)
        if not tool:
            return self._error(f"tool_not_found: {action}")

        return self._safe_execute(tool, data, state)

    # =========================
    def _is_valid_decision(self, decision):
        return isinstance(decision, dict) and decision.get("action")

    # =========================
    def _sanitize_data(self, action, data):
        if data is None:
            return {}

        if isinstance(data, str):
            return self._sanitize_string_input(action, data)

        if isinstance(data, dict):
            return self._normalize_data_fields(action, data)

        return {"input": str(data)}

    # =========================
    def _normalize_data_fields(self, action, data):
        if not isinstance(data, dict):
            return data

        if action == "write_file":
            if "path" not in data:
                if "file_path" in data:
                    data["path"] = data.pop("file_path")
                elif "filename" in data:
                    data["path"] = data.pop("filename")
                elif "file" in data:
                    data["path"] = data.pop("file")
            # Converter lista para string se necessário
            if isinstance(data.get("path"), list) and data["path"]:
                data["path"] = (
                    data["path"][0]
                    if len(data["path"]) == 1
                    else "/".join(map(str, data["path"]))
                )

        if action == "run_python":
            if "code" not in data and "file_path" in data:
                file_path = data.get("file_path")
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        data["code"] = f.read()
                except Exception:
                    pass

        if action in ["create_folder", "delete_file", "read_file"]:
            if "path" not in data:
                if "folder" in data:
                    data["path"] = data.pop("folder")
                elif "directory" in data:
                    data["path"] = data.pop("directory")
            # Converter lista para string se necessário
            if isinstance(data.get("path"), list) and data["path"]:
                data["path"] = (
                    data["path"][0]
                    if len(data["path"]) == 1
                    else "/".join(map(str, data["path"]))
                )

        return data

    # =========================
    def _sanitize_string_input(self, action, data):
        data = data.strip()

        if action == "write_file":
            if "|" not in data:
                return None
            path, content = data.split("|", 1)
            return {"path": path.strip(), "content": content}

        if action in ["create_folder", "delete_file"]:
            return {"path": data}

        if action == "run_python":
            return {"code": data}

        return {"input": data}

    # =========================
    def _execute_specialist(self, action, state):
        try:
            return self._success(f"specialist_executed: {action}")
        except Exception as e:
            return self._error(f"specialist_error: {str(e)}")

    # =========================
    def _safe_execute(self, tool, data, state):
        attempts = 0

        while attempts <= self.max_retries:
            try:
                result = tool(data, state)

                if isinstance(result, dict) and result.get("status") == "error":
                    error_message = result.get("error") or result.get("output")
                    print(f"[TOOL ERROR] {error_message}")

                return self._normalize_result(result)

            except Exception as e:
                attempts += 1
                traceback.print_exc()

                if attempts > self.max_retries:
                    return self._error(f"execution_failed: {str(e)}")

    # =========================
    def _normalize_result(self, result):
        if isinstance(result, dict):
            normalized = {
                "status": result.get("status") or ("error" if result.get("error") else "success"),
                "output": result.get("output"),
                "error": result.get("error"),
            }

            for key, value in result.items():
                if key not in normalized:
                    normalized[key] = value

            if normalized["status"] == "success" and normalized["output"] is None:
                normalized["output"] = ""

            if normalized["status"] == "error" and normalized["error"] is None:
                normalized["error"] = str(normalized.get("output") or "unknown_error")

            return normalized

        return {"status": "success", "output": result, "error": None}

    # =========================
    def _error(self, message):
        return {"status": "error", "output": None, "error": message}

    def _success(self, message):
        return {"status": "success", "output": message, "error": None}
