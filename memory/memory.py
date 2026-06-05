import hashlib
import json
import os
import re
import time
import threading


class Memory:
    """Persistent memory with facts, episodes, skills, and lessons.

    The public surface stays compatible with the old Memory class:
    `build_context`, `store_step`, `get_fact`, and `clear` still work as before.
    New structured memory is added under `context["memory"]`.
    """

    def __init__(
        self,
        vector_store,
        retriever,
        persist_path="data/vectors/memory",
        max_episodes=200,
        max_lessons=100,
        max_skills=100,
        require_confirmation=False,
    ):
        self.vector_store = vector_store
        self.retriever = retriever
        self.persist_path = persist_path
        self.max_episodes = max(1, int(max_episodes or 200))
        self.max_lessons = max(1, int(max_lessons or 100))
        self.max_skills = max(1, int(max_skills or 100))

        # Backward-compatible facts view: context["facts"]["user_name"] == "Ana".
        self.facts = {}

        # Structured continuous-learning memory.
        self.fact_metadata = {}
        self.episodes = []
        self.skills = {}
        self.lessons = []

        # se True, fatos extraídos automaticamente são gravados como 'pending_*' até confirmação
        self.require_confirmation = bool(require_confirmation)

        self._load_if_exists()
        # Background save helpers
        try:
            self._save_lock = threading.Lock()
        except Exception:
            self._save_lock = None
        self._save_thread = None

    def store_step(self, step, result, feedback):
        try:
            text = self._format_step(step, result, feedback)
            self._add_vector_memory(text, metadata={"kind": "step"})
            self._extract_and_store_facts(text)
            episode = self.remember_episode(
                task=self._step_action(step),
                step=step,
                result=result,
                feedback=feedback,
                source="store_step",
            )
            self._learn_from_step(step, result, feedback, episode)
            self._save()
        except Exception:
            pass

    def build_context(self, goal, state):
        retrieved = self._safe_retrieve(goal)
        history = self._extract_recent_history(state)

        facts_before = self._facts_signature()
        self._extract_and_store_facts(goal)
        if self._facts_signature() != facts_before:
            self._save()

        structured = self._structured_context(goal)
        return {
            "goal": goal,
            "recent_history": history,
            "retrieved_memory": retrieved + self._format_structured_for_retrieval(structured),
            "facts": self.facts.copy(),
            "memory": structured,
            "episodes": structured["episodes"],
            "skills": structured["skills"],
            "lessons": structured["lessons"],
        }

    def get_fact(self, key, default=None):
        return self.facts.get(key, default)

    def remember_fact(
        self,
        key,
        value,
        confidence=0.9,
        source="user",
        validated_at=None,
    ):
        key = str(key or "").strip()
        if not key:
            return None

        now = self._now()
        old_value = self.facts.get(key)
        self.facts[key] = value

        metadata = self.fact_metadata.get(key, {})
        metadata.setdefault("created_at", now)
        metadata["updated_at"] = now
        metadata["source"] = source
        metadata["confidence"] = self._bounded_confidence(confidence)
        metadata["last_validated_at"] = validated_at or now

        if old_value is not None and old_value != value:
            metadata["corrections"] = int(metadata.get("corrections", 0) or 0) + 1
            history = metadata.setdefault("history", [])
            history.append(
                {
                    "value": old_value,
                    "replaced_at": now,
                    "replaced_by": value,
                    "source": source,
                }
            )
            metadata["history"] = history[-20:]

        self.fact_metadata[key] = metadata
        return {"key": key, "value": value, "metadata": metadata.copy()}

    def remember_episode(
        self,
        task,
        step=None,
        result=None,
        feedback=None,
        confidence=None,
        source="system",
        tags=None,
    ):
        now = self._now()
        status = self._status(result)
        inferred_confidence = 0.85 if status == "success" else 0.45
        if str(feedback).lower() in {"fail", "error", "failed"}:
            inferred_confidence = min(inferred_confidence, 0.35)

        record = {
            "id": self._record_id("episode", task, step, result, now),
            "kind": "episode",
            "task": self._json_safe(task),
            "step": self._json_safe(step),
            "result": self._json_safe(result),
            "feedback": self._json_safe(feedback),
            "status": status,
            "summary": self._episode_summary(task, step, result, feedback),
            "confidence": self._bounded_confidence(
                inferred_confidence if confidence is None else confidence
            ),
            "source": source,
            "created_at": now,
            "last_validated_at": now if status == "success" else None,
            "tags": list(tags or []),
        }

        self.episodes.append(record)
        self._prune_episodes()
        self._add_vector_memory(
            self._format_record_for_vector(record),
            metadata={"kind": "episode", "id": record["id"]},
        )
        return record

    def remember_skill(
        self,
        name,
        procedure,
        trigger=None,
        confidence=0.75,
        source="learned",
        evidence=None,
    ):
        key = self._memory_key(name)
        if not key:
            return None

        now = self._now()
        existing = self.skills.get(key, {})
        success_count = int(existing.get("success_count", 0) or 0) + 1
        old_confidence = float(existing.get("confidence", 0.0) or 0.0)
        new_confidence = max(old_confidence, self._bounded_confidence(confidence))
        if old_confidence:
            new_confidence = min(1.0, new_confidence + 0.03)

        record = {
            "id": existing.get("id") or self._record_id("skill", key),
            "kind": "skill",
            "name": str(name),
            "trigger": str(trigger or name),
            "procedure": self._json_safe(procedure),
            "confidence": round(new_confidence, 4),
            "source": source,
            "evidence": self._json_safe(evidence),
            "success_count": success_count,
            "failure_count": int(existing.get("failure_count", 0) or 0),
            "created_at": existing.get("created_at") or now,
            "updated_at": now,
            "last_validated_at": now,
        }

        self.skills[key] = record
        self._prune_skills()
        self._add_vector_memory(
            self._format_record_for_vector(record),
            metadata={"kind": "skill", "id": record["id"]},
        )
        return record

    def remember_lesson(
        self,
        problem,
        solution,
        confidence=0.65,
        source="learned",
        evidence=None,
    ):
        problem_text = str(problem or "").strip()
        solution_text = str(solution or "").strip()
        if not problem_text or not solution_text:
            return None

        key = self._record_id("lesson", problem_text, solution_text)
        now = self._now()
        existing = next((item for item in self.lessons if item.get("id") == key), None)

        if existing:
            existing["confidence"] = min(
                1.0,
                max(float(existing.get("confidence", 0.0) or 0.0), confidence) + 0.02,
            )
            existing["updated_at"] = now
            existing["last_validated_at"] = now
            existing["observations"] = int(existing.get("observations", 1) or 1) + 1
            existing["evidence"] = self._json_safe(evidence)
            record = existing
        else:
            record = {
                "id": key,
                "kind": "lesson",
                "problem": problem_text,
                "solution": solution_text,
                "confidence": self._bounded_confidence(confidence),
                "source": source,
                "evidence": self._json_safe(evidence),
                "observations": 1,
                "created_at": now,
                "updated_at": now,
                "last_validated_at": None,
            }
            self.lessons.append(record)

        self._prune_lessons()
        self._add_vector_memory(
            self._format_record_for_vector(record),
            metadata={"kind": "lesson", "id": record["id"]},
        )
        return record

    def get_memory_snapshot(self):
        return {
            "facts": self.facts.copy(),
            "fact_metadata": self._json_safe(self.fact_metadata),
            "episodes": list(self.episodes),
            "skills": dict(self.skills),
            "lessons": list(self.lessons),
        }

    def validate_memory(self, kind, identifier, confidence_delta=0.05, source="validation"):
        """Mark a memory item as still valid and slightly increase confidence."""
        record = self._find_memory_record(kind, identifier)
        if record is None:
            return None

        now = self._now()
        delta = max(0.0, self._bounded_confidence(confidence_delta))

        if isinstance(record, tuple) and record[0] == "fact":
            key = record[1]
            metadata = self.fact_metadata.setdefault(key, {})
            metadata["last_validated_at"] = now
            metadata["validated_by"] = source
            metadata["confidence"] = min(
                1.0,
                self._bounded_confidence(metadata.get("confidence", 0.5)) + delta,
            )
            self._save()
            return {"key": key, "value": self.facts.get(key), "metadata": metadata.copy()}

        record["last_validated_at"] = now
        record["updated_at"] = now
        record["validated_by"] = source
        record["validation_count"] = int(record.get("validation_count", 0) or 0) + 1
        record["confidence"] = min(
            1.0,
            self._bounded_confidence(record.get("confidence", 0.5)) + delta,
        )
        self._save()
        return record

    def forget_memory(self, kind, identifier=None, reason="manual"):
        """Remove a memory item or an entire memory kind."""
        kind = self._normalize_kind(kind)
        removed = []

        if kind == "fact":
            keys = list(self.facts.keys()) if identifier is None else [str(identifier)]
            for key in keys:
                if key in self.facts:
                    removed.append({"kind": "fact", "id": key, "reason": reason})
                    self.facts.pop(key, None)
                    self.fact_metadata.pop(key, None)

        elif kind == "skill":
            if identifier is None:
                removed = [
                    {"kind": "skill", "id": item.get("id"), "reason": reason}
                    for item in self.skills.values()
                ]
                self.skills = {}
            else:
                key = self._resolve_skill_key(identifier)
                if key and key in self.skills:
                    item = self.skills.pop(key)
                    removed.append({"kind": "skill", "id": item.get("id"), "reason": reason})

        elif kind in {"episode", "lesson"}:
            collection = self.episodes if kind == "episode" else self.lessons
            if identifier is None:
                removed = [
                    {"kind": kind, "id": item.get("id"), "reason": reason}
                    for item in collection
                ]
                if kind == "episode":
                    self.episodes = []
                else:
                    self.lessons = []
            else:
                kept = []
                for item in collection:
                    if self._record_matches(item, identifier):
                        removed.append({"kind": kind, "id": item.get("id"), "reason": reason})
                    else:
                        kept.append(item)
                if kind == "episode":
                    self.episodes = kept
                else:
                    self.lessons = kept

        if removed:
            self._save()
        return removed

    def clear(self):
        if hasattr(self.vector_store, "clear"):
            self.vector_store.clear()
        elif hasattr(self.vector_store, "vectors"):
            self.vector_store.vectors = []
        self.facts = {}
        self.fact_metadata = {}
        self.episodes = []
        self.skills = {}
        self.lessons = []
        self._save()

    def _save(self):
        # Persist memory state. Use synchronous save by default to avoid
        # race conditions where callers expect persistence to be available
        # immediately after calling APIs that trigger a save (tests and
        # short-lived processes). For production, set
        # `ASSISTENTE_BACKGROUND_SAVE=1` to restore background behavior.
        try:
            bg = str(os.environ.get("ASSISTENTE_BACKGROUND_SAVE", "0")).strip().lower() in ("1", "true", "yes")
            if bg:
                if getattr(self, "_save_thread", None) and self._save_thread.is_alive():
                    return
                t = threading.Thread(target=self._save_sync, daemon=True)
                self._save_thread = t
                t.start()
                return

            # Default: synchronous save for reliability
            self._save_sync()
        except Exception:
            pass

    def _save_sync(self):
        lock = getattr(self, "_save_lock", None)
        if lock is None:
            try:
                directory = os.path.dirname(self.persist_path)
                if directory:
                    os.makedirs(directory, exist_ok=True)
                try:
                    self.vector_store.save(self.persist_path)
                except Exception:
                    pass
                try:
                    self._save_facts()
                except Exception:
                    pass
                try:
                    self._save_learning_state()
                except Exception:
                    pass
            except Exception:
                pass
            return

        with lock:
            try:
                directory = os.path.dirname(self.persist_path)
                if directory:
                    os.makedirs(directory, exist_ok=True)
                try:
                    self.vector_store.save(self.persist_path)
                except Exception:
                    pass
                try:
                    self._save_facts()
                except Exception:
                    pass
                try:
                    self._save_learning_state()
                except Exception:
                    pass
            except Exception:
                pass

    def _load_if_exists(self):
        try:
            if os.path.exists(self.persist_path + ".index") or os.path.exists(
                self.persist_path + ".data.npz"
            ):
                self.vector_store.load(self.persist_path)
            self._load_facts()
            self._load_learning_state()
        except Exception:
            pass

    def _format_step(self, step, result, feedback):
        return f"STEP: {step} RESULT: {result} FEEDBACK: {feedback}"

    def _safe_retrieve(self, goal):
        try:
            return self._retrieved_list(self.retriever.retrieve(goal))
        except TypeError:
            try:
                return self._retrieved_list(self.retriever.retrieve(goal, 5))
            except Exception:
                return []
        except Exception:
            return []

    def _extract_recent_history(self, state):
        if not isinstance(state, dict):
            return []
        return state.get("history", [])[-5:]

    def _retrieved_list(self, value):
        if value is None:
            return []
        if isinstance(value, list):
            return value
        if isinstance(value, tuple):
            return list(value)
        return []

    def _extract_and_store_facts(self, text):
        if not isinstance(text, str):
            text = str(text)

        name_patterns = [
            r"\bmeu nome (?:e|é|Ã©|ÃƒÂ©)\s+([^\s.,;:!?()[\]{}]+)",
            r"\bme chamo\s+([^\s.,;:!?()[\]{}]+)",
            r"\bpode me chamar de\s+([^\s.,;:!?()[\]{}]+)",
        ]

        for pattern in name_patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                key = "pending_user_name" if getattr(self, "require_confirmation", False) else "user_name"
                self.remember_fact(
                    key,
                    self._clean_fact_value(match.group(1)),
                    confidence=0.95,
                    source=("user_statement_pending" if key.startswith("pending_") else "user_statement"),
                )
                break

        like_patterns = [
            r"\bgosto de\s+([^.;,\n]+)",
            r"\beu gosto de\s+([^.;,\n]+)",
        ]

        for pattern in like_patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                value = self._clean_fact_value(match.group(1))
                if value:
                    likes = list(self.facts.get("likes", []))
                    if value not in likes:
                        likes.append(value)
                    self.remember_fact(
                        "likes",
                        likes,
                        confidence=0.85,
                        source="user_statement",
                    )

        match = re.search(
            r"\bgosto de programar em\s+([A-Za-z0-9_+#.-]+)",
            text,
            flags=re.IGNORECASE,
        )
        if match:
            self.remember_fact(
                "programming_language",
                self._clean_fact_value(match.group(1)),
                confidence=0.9,
                source="user_statement",
            )

    def _learn_from_step(self, step, result, feedback, episode):
        if not isinstance(step, dict):
            return

        action = str(step.get("action") or "").strip()
        if not action:
            return

        status = self._status(result)
        failed = status != "success" or str(feedback).lower() in {"fail", "error", "failed"}

        if failed:
            error = ""
            if isinstance(result, dict):
                error = str(result.get("error") or result.get("output") or "unknown_error")
            problem = f"{action} failed: {error or 'unknown_error'}"
            solution = "Review the action parameters, keep paths inside the safe workspace, and retry with a smaller step."
            self.remember_lesson(
                problem,
                solution,
                confidence=0.6,
                source="failed_step",
                evidence=episode,
            )
            self._mark_skill_failure(action)
            return

        self.remember_skill(
            name=f"use_{action}",
            trigger=f"task requiring {action}",
            procedure=self._procedure_for_step(step),
            confidence=0.75,
            source="successful_step",
            evidence=episode,
        )

    def _procedure_for_step(self, step):
        action = step.get("action")
        data = step.get("data", {}) if isinstance(step.get("data"), dict) else {}
        fields = sorted(data.keys())
        if fields:
            return {
                "steps": [
                    {
                        "action": action,
                        "required_fields": fields,
                    }
                ]
            }
        return {"steps": [{"action": action}]}

    def _mark_skill_failure(self, action):
        key = self._memory_key(f"use_{action}")
        if key not in self.skills:
            return
        record = self.skills[key]
        record["failure_count"] = int(record.get("failure_count", 0) or 0) + 1
        record["confidence"] = max(0.0, round(float(record.get("confidence", 0.0)) - 0.05, 4))
        record["updated_at"] = self._now()

    def _structured_context(self, goal):
        return {
            "facts": self.facts.copy(),
            "fact_metadata": self._json_safe(self.fact_metadata),
            "episodes": self._rank_records(goal, self.episodes, ["summary", "task"], top_k=5),
            "skills": self._rank_records(goal, self.skills.values(), ["name", "trigger"], top_k=5),
            "lessons": self._rank_records(goal, self.lessons, ["problem", "solution"], top_k=5),
        }

    def _rank_records(self, query, records, fields, top_k=5):
        query_tokens = self._tokens(query)
        scored = []
        for record in records:
            text = " ".join(str(record.get(field, "")) for field in fields)
            overlap = len(query_tokens & self._tokens(text))
            confidence = float(record.get("confidence", 0.0) or 0.0)
            recency = float(record.get("updated_at", record.get("created_at", 0.0)) or 0.0)
            if overlap <= 0 and confidence < 0.9:
                continue
            scored.append(((overlap, confidence, recency), record))

        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [record for _, record in scored[:top_k]]

    def _format_structured_for_retrieval(self, structured):
        items = []
        for skill in structured.get("skills", []):
            items.append(f"SKILL {skill.get('name')}: {skill.get('procedure')}")
        for lesson in structured.get("lessons", []):
            items.append(
                f"LESSON problem={lesson.get('problem')} solution={lesson.get('solution')}"
            )
        return items

    def _format_record_for_vector(self, record):
        if record.get("kind") == "skill":
            return (
                f"SKILL {record.get('name')} TRIGGER {record.get('trigger')} "
                f"PROCEDURE {record.get('procedure')}"
            )
        if record.get("kind") == "lesson":
            return (
                f"LESSON PROBLEM {record.get('problem')} "
                f"SOLUTION {record.get('solution')}"
            )
        return f"EPISODE {record.get('summary')} STATUS {record.get('status')}"

    def _add_vector_memory(self, text, metadata=None):
        add = getattr(self.vector_store, "add", None)
        if callable(add):
            try:
                add(text, metadata=metadata or {})
            except TypeError:
                add(text)

    def _episode_summary(self, task, step, result, feedback):
        action = self._step_action(step) or str(task or "task")
        status = self._status(result)
        output = ""
        if isinstance(result, dict):
            output = result.get("output") or result.get("error") or ""
        return f"{action} -> {status}; feedback={feedback}; output={str(output)[:160]}"

    def _step_action(self, step):
        return step.get("action") if isinstance(step, dict) else None

    def _status(self, result):
        if isinstance(result, dict):
            return str(result.get("status") or "success").lower()
        return "success" if result is not None else "unknown"

    def _prune_episodes(self):
        self.episodes.sort(
            key=lambda item: (
                float(item.get("confidence", 0.0) or 0.0),
                float(item.get("created_at", 0.0) or 0.0),
            ),
            reverse=True,
        )
        self.episodes = self.episodes[: self.max_episodes]

    def _prune_lessons(self):
        self.lessons.sort(
            key=lambda item: (
                float(item.get("confidence", 0.0) or 0.0),
                int(item.get("observations", 1) or 1),
                float(item.get("updated_at", item.get("created_at", 0.0)) or 0.0),
            ),
            reverse=True,
        )
        self.lessons = self.lessons[: self.max_lessons]

    def _prune_skills(self):
        if len(self.skills) <= self.max_skills:
            return
        ordered = sorted(
            self.skills.items(),
            key=lambda pair: (
                float(pair[1].get("confidence", 0.0) or 0.0),
                int(pair[1].get("success_count", 0) or 0),
                float(pair[1].get("updated_at", 0.0) or 0.0),
            ),
            reverse=True,
        )
        self.skills = dict(ordered[: self.max_skills])

    def _find_memory_record(self, kind, identifier):
        kind = self._normalize_kind(kind)
        if identifier is None:
            return None

        if kind == "fact":
            key = str(identifier)
            if key in self.facts:
                return ("fact", key)
            return None

        if kind == "skill":
            key = self._resolve_skill_key(identifier)
            return self.skills.get(key) if key else None

        collection = self.episodes if kind == "episode" else self.lessons
        if kind not in {"episode", "lesson"}:
            return None

        for record in collection:
            if self._record_matches(record, identifier):
                return record
        return None

    def _normalize_kind(self, kind):
        normalized = self._memory_key(kind)
        aliases = {
            "facts": "fact",
            "fact_metadata": "fact",
            "episodes": "episode",
            "skills": "skill",
            "lessons": "lesson",
        }
        return aliases.get(normalized, normalized)

    def _resolve_skill_key(self, identifier):
        key = self._memory_key(identifier)
        if key in self.skills:
            return key
        for candidate, record in self.skills.items():
            if self._record_matches(record, identifier):
                return candidate
        return None

    def _record_matches(self, record, identifier):
        needle = str(identifier)
        if str(record.get("id")) == needle:
            return True
        for field in ("name", "trigger", "problem", "solution", "summary", "task"):
            value = record.get(field)
            if value is not None and self._memory_key(value) == self._memory_key(needle):
                return True
        return False

    def _facts_signature(self):
        try:
            return json.dumps(self.facts, ensure_ascii=False, sort_keys=True)
        except TypeError:
            return str(self.facts)

    def _clean_fact_value(self, value):
        return str(value).strip(" '\".,;:!?()[]{}")

    def _facts_path(self):
        return self.persist_path + ".facts.json"

    def _learning_path(self):
        return self.persist_path + ".learning.json"

    def _save_facts(self):
        with open(self._facts_path(), "w", encoding="utf-8") as f:
            json.dump(self.facts, f, ensure_ascii=False, indent=2)

    def _save_learning_state(self):
        data = {
            "schema": "memory_v2",
            "facts": self.facts,
            "fact_metadata": self.fact_metadata,
            "episodes": self.episodes,
            "skills": self.skills,
            "lessons": self.lessons,
        }
        with open(self._learning_path(), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _load_facts(self):
        path = self._facts_path()
        if not os.path.exists(path):
            return

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, dict):
            self.facts = data

    def _load_learning_state(self):
        path = self._learning_path()
        if not os.path.exists(path):
            return

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, dict):
            return

        if isinstance(data.get("facts"), dict):
            self.facts.update(data["facts"])
        if isinstance(data.get("fact_metadata"), dict):
            self.fact_metadata = data["fact_metadata"]
        if isinstance(data.get("episodes"), list):
            self.episodes = data["episodes"][-self.max_episodes :]
        if isinstance(data.get("skills"), dict):
            self.skills = dict(list(data["skills"].items())[-self.max_skills :])
        if isinstance(data.get("lessons"), list):
            self.lessons = data["lessons"][-self.max_lessons :]

    def _record_id(self, *parts):
        digest = hashlib.sha256(
            "|".join(str(part) for part in parts).encode("utf-8", errors="replace")
        ).hexdigest()
        return digest[:16]

    def _memory_key(self, value):
        return re.sub(r"[^a-z0-9_]+", "_", str(value or "").strip().lower()).strip("_")

    def _tokens(self, value):
        return set(re.findall(r"[A-Za-z0-9_+#.-]+", str(value or "").lower()))

    def _bounded_confidence(self, value):
        try:
            confidence = float(value)
        except (TypeError, ValueError):
            confidence = 0.5
        return round(max(0.0, min(1.0, confidence)), 4)

    def _json_safe(self, value):
        try:
            json.dumps(value, ensure_ascii=False)
            return value
        except TypeError:
            return str(value)

    def _now(self):
        return time.time()
