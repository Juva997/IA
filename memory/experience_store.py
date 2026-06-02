import json
import os
import time


class ExperienceStore:
    def __init__(self, memory=None, path=None, max_items=1000, min_reuse_score=0.5):
        self.memory = memory
        self.path = path
        self.max_items = max(1, int(max_items or 1000))
        self.min_reuse_score = float(min_reuse_score)
        self.experiences = []
        self._load()

    def record(self, task, plan, result, evaluation, metadata=None):
        experience = {
            "task": self._task_text(task),
            "plan": self._json_safe(plan),
            "result": self._json_safe(result),
            "score": float(getattr(evaluation, "score", 0.0)),
            "passed": bool(getattr(evaluation, "passed", False)),
            "feedback": getattr(evaluation, "feedback", "unknown"),
            "metadata": self._json_safe(metadata or {}),
            "created_at": time.time(),
        }

        self.experiences.append(experience)
        if len(self.experiences) > self.max_items:
            self.experiences = self.experiences[-self.max_items :]

        self._store_in_memory(experience)
        self._save()
        return experience

    def retrieve_similar(self, task, top_k=5, min_score=None):
        query = self._task_text(task)
        threshold = self.min_reuse_score if min_score is None else float(min_score)
        ranked = self._rank_experiences(query, top_k, threshold)
        if ranked:
            return ranked

        from_memory = self._retrieve_from_memory(query, top_k)
        return from_memory[:top_k]

    def summarize_success_patterns(self, top_k=5):
        successful = [
            item
            for item in self.experiences
            if item.get("passed") and float(item.get("score", 0.0)) >= self.min_reuse_score
        ]
        successful.sort(
            key=lambda item: (float(item.get("score", 0.0)), item.get("created_at", 0.0)),
            reverse=True,
        )
        patterns = []
        for item in successful[:top_k]:
            patterns.append(
                {
                    "task": item.get("task"),
                    "score": item.get("score"),
                    "feedback": item.get("feedback"),
                    "plan": item.get("plan"),
                }
            )
        return patterns

    def learning_metrics(self, window=20):
        history = self.experiences[-max(1, int(window or 20)) :]
        if not history:
            return {
                "learning_rate": 0.0,
                "success_trend": 0.0,
                "retry_efficiency": 0.0,
                "knowledge_reuse": 0.0,
            }

        scores = [float(item.get("score", 0.0)) for item in history]
        midpoint = max(1, len(scores) // 2)
        early = scores[:midpoint]
        late = scores[midpoint:] or scores

        early_success = self._success_rate(history[:midpoint])
        late_success = self._success_rate(history[midpoint:] or history)
        attempts = [self._attempt_count(item) for item in history]
        reused = [
            item
            for item in history
            if int(item.get("metadata", {}).get("used_experiences", 0) or 0) > 0
        ]

        return {
            "learning_rate": round(self._mean(late) - self._mean(early), 4),
            "success_trend": round(late_success - early_success, 4),
            "retry_efficiency": round(1.0 / max(1.0, self._mean(attempts)), 4),
            "knowledge_reuse": round(len(reused) / len(history), 4),
        }

    def _retrieve_from_memory(self, query, top_k):
        if not self.memory:
            return []

        retriever = getattr(self.memory, "retriever", None)
        retrieve = getattr(retriever, "retrieve", None)
        if callable(retrieve):
            try:
                return retrieve(query, top_k)
            except TypeError:
                return retrieve(query)
            except Exception:
                return []

        vector_store = getattr(self.memory, "vector_store", None)
        search = getattr(vector_store, "search", None)
        if callable(search):
            try:
                results = search(query, top_k)
            except Exception:
                return []
            return [item.get("text", item) if isinstance(item, dict) else item for item in results]

        return []

    def _rank_experiences(self, query, top_k, min_score):
        query_tokens = set(str(query).lower().split())
        scored = []
        for item in self.experiences:
            task_tokens = set(str(item.get("task", "")).lower().split())
            overlap = len(query_tokens & task_tokens)
            if not overlap:
                continue

            score = float(item.get("score", 0.0))
            if score < min_score:
                continue

            success_boost = 1.25 if item.get("passed") else 1.0
            recency = float(item.get("created_at", 0.0))
            rank = (overlap * (0.5 + score) * success_boost, recency)
            enriched = dict(item)
            enriched["reuse_rank"] = round(rank[0], 4)
            scored.append((rank, enriched))

        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [item for _, item in scored[:top_k]]

    def _store_in_memory(self, experience):
        if not self.memory:
            return

        text = self._format_for_retrieval(experience)
        store_step = getattr(self.memory, "store_step", None)
        if callable(store_step):
            try:
                store_step(
                    {"action": "experience", "data": {"task": experience["task"]}},
                    {"status": "success", "output": text},
                    experience["feedback"],
                )
                return
            except Exception:
                pass

        vector_store = getattr(self.memory, "vector_store", None)
        add = getattr(vector_store, "add", None)
        if callable(add):
            try:
                add(text, metadata=experience)
            except Exception:
                pass

    def _format_for_retrieval(self, experience):
        return (
            f"TASK: {experience.get('task')} "
            f"SCORE: {experience.get('score')} "
            f"FEEDBACK: {experience.get('feedback')} "
            f"PLAN: {experience.get('plan')}"
        )

    def _load(self):
        if not self.path or not os.path.exists(self.path):
            return
        try:
            with open(self.path, "r", encoding="utf-8") as file:
                data = json.load(file)
            if isinstance(data, list):
                self.experiences = data[-self.max_items :]
        except Exception:
            self.experiences = []

    def _save(self):
        if not self.path:
            return
        try:
            directory = os.path.dirname(self.path)
            if directory:
                os.makedirs(directory, exist_ok=True)
            with open(self.path, "w", encoding="utf-8") as file:
                json.dump(self.experiences, file, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _task_text(self, task):
        if isinstance(task, dict):
            return str(task.get("input") or task.get("task") or task.get("goal") or task)
        return str(task)

    def _json_safe(self, value):
        try:
            json.dumps(value, ensure_ascii=False)
            return value
        except TypeError:
            return str(value)

    def _attempt_count(self, item):
        metadata = item.get("metadata", {}) if isinstance(item, dict) else {}
        return int(metadata.get("attempts", 1) or 1)

    def _success_rate(self, history):
        if not history:
            return 0.0
        return sum(1 for item in history if item.get("passed")) / len(history)

    def _mean(self, values):
        return sum(values) / len(values) if values else 0.0
