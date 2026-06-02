class Critic:
    def __init__(self):
        pass

    def evaluate(self, result):
        if not isinstance(result, dict):
            return "fail"

        status = result.get("status")

        if status == "success":
            return "success"

        # 🔥 DEBUG REAL
        error = result.get("error", "unknown_error")
        print(f"[CRITIC] Error: {error}")

        return "fail"
