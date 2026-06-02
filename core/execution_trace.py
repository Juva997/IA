import time
import uuid


class ExecutionTracer:
    def __init__(self, trace_id=None, clock=None):
        self.trace_id = trace_id or uuid.uuid4().hex
        self.clock = clock or time.perf_counter
        self.started_at = self.clock()
        self.events = []

    def add_event(self, name, data=None):
        event = {
            "event": str(name),
            "time": round(self.clock() - self.started_at, 6),
            "data": data or {},
        }
        self.events.append(event)
        return event

    def start_step(self, step, iteration=None):
        return {
            "step_id": uuid.uuid4().hex,
            "step": step,
            "iteration": iteration,
            "started_at": self.clock(),
        }

    def end_step(self, span, result):
        duration = max(0.0, self.clock() - span["started_at"])
        event = {
            "event": "step",
            "step_id": span["step_id"],
            "iteration": span.get("iteration"),
            "action": self._action(span.get("step")),
            "status": self._status(result),
            "duration": round(duration, 6),
            "error": self._error(result),
            "step": span.get("step"),
        }
        self.events.append(event)
        return event

    def to_dict(self):
        duration = max(0.0, self.clock() - self.started_at)
        step_events = [event for event in self.events if event.get("event") == "step"]
        failures = [event for event in step_events if event.get("status") == "error"]
        return {
            "trace_id": self.trace_id,
            "duration": round(duration, 6),
            "steps": len(step_events),
            "failures": len(failures),
            "first_error": failures[0]["error"] if failures else None,
            "timeline": list(self.events),
        }

    def _action(self, step):
        if isinstance(step, dict):
            return step.get("action")
        return None

    def _status(self, result):
        if isinstance(result, dict):
            return str(result.get("status", "success")).lower()
        return "success"

    def _error(self, result):
        if isinstance(result, dict):
            return result.get("error")
        return None
