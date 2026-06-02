from memory.memory import Memory


class FakeVectorStore:
    def __init__(self):
        self.items = []

    def add(self, text, metadata=None):
        self.items.append((text, metadata))

    def save(self, path):
        return None

    def load(self, path):
        return None

    def clear(self):
        self.items = []


class FakeRetriever:
    def retrieve(self, query):
        return []


def test_memory_extracts_user_facts_with_accents(tmp_path):
    memory = Memory(
        FakeVectorStore(),
        FakeRetriever(),
        persist_path=str(tmp_path / "memory"),
    )

    context = memory.build_context(
        "lembre-se que meu nome é João e gosto de programar em Python",
        {"history": []},
    )

    assert context["facts"]["user_name"] == "João"
    assert context["facts"]["programming_language"] == "Python"
    assert "programar em Python" in context["facts"]["likes"]


def test_memory_persists_facts(tmp_path):
    path = str(tmp_path / "memory")
    memory = Memory(FakeVectorStore(), FakeRetriever(), persist_path=path)
    memory.build_context("me chamo Ana", {"history": []})

    restored = Memory(FakeVectorStore(), FakeRetriever(), persist_path=path)

    assert restored.get_fact("user_name") == "Ana"


def test_memory_v2_learns_episode_and_skill_from_success(tmp_path):
    memory = Memory(FakeVectorStore(), FakeRetriever(), persist_path=str(tmp_path / "memory"))

    memory.store_step(
        {"action": "write_file", "data": {"path": "out.txt", "content": "ok"}},
        {"status": "success", "output": "arquivo criado"},
        "pass",
    )

    snapshot = memory.get_memory_snapshot()
    assert len(snapshot["episodes"]) == 1
    assert "use_write_file" in snapshot["skills"]

    context = memory.build_context("task requiring write_file", {"history": []})

    assert context["memory"]["skills"][0]["name"] == "use_write_file"
    assert any("SKILL use_write_file" in item for item in context["retrieved_memory"])


def test_memory_v2_records_lesson_and_degrades_skill_after_failure(tmp_path):
    memory = Memory(FakeVectorStore(), FakeRetriever(), persist_path=str(tmp_path / "memory"))
    memory.remember_skill("use_write_file", {"steps": [{"action": "write_file"}]}, confidence=0.8)

    memory.store_step(
        {"action": "write_file", "data": {"path": "../escape.txt"}},
        {"status": "error", "error": "path_outside_safe_root"},
        "fail",
    )

    snapshot = memory.get_memory_snapshot()
    skill = snapshot["skills"]["use_write_file"]

    assert skill["failure_count"] == 1
    assert skill["confidence"] < 0.8
    assert snapshot["lessons"]
    assert "path_outside_safe_root" in snapshot["lessons"][0]["problem"]


def test_memory_v2_persists_structured_learning_state(tmp_path):
    path = str(tmp_path / "memory")
    memory = Memory(FakeVectorStore(), FakeRetriever(), persist_path=path)

    memory.build_context("me chamo Bia", {"history": []})
    memory.remember_skill(
        "validate_project",
        {"steps": ["python -m pytest -q", "python -m benchmark.runner --dataset full"]},
        trigger="testar projeto inteiro",
        confidence=0.9,
        source="unit_test",
    )
    memory.remember_lesson(
        "dataset all nao inclui suites grandes",
        "use dataset full para validar tudo",
        confidence=0.9,
        source="unit_test",
    )
    memory._save()

    restored = Memory(FakeVectorStore(), FakeRetriever(), persist_path=path)
    context = restored.build_context("testar projeto inteiro com benchmark full", {"history": []})

    assert restored.get_fact("user_name") == "Bia"
    assert "validate_project" in restored.get_memory_snapshot()["skills"]
    assert context["memory"]["lessons"][0]["solution"] == "use dataset full para validar tudo"


def test_memory_v2_validates_and_forgets_records(tmp_path):
    memory = Memory(FakeVectorStore(), FakeRetriever(), persist_path=str(tmp_path / "memory"))
    memory.remember_fact("user_name", "Caio", confidence=0.5)
    skill = memory.remember_skill("validate_project", {"steps": ["pytest"]}, confidence=0.6)
    lesson = memory.remember_lesson("falha antiga", "corrigir entrada", confidence=0.6)

    fact = memory.validate_memory("fact", "user_name", confidence_delta=0.2)
    validated_skill = memory.validate_memory("skill", skill["id"], confidence_delta=0.2)
    validated_lesson = memory.validate_memory("lesson", lesson["id"], confidence_delta=0.2)

    assert fact["metadata"]["confidence"] == 0.7
    assert validated_skill["confidence"] == 0.8
    assert validated_lesson["confidence"] == 0.8

    removed = memory.forget_memory("skill", "validate_project")

    assert removed
    assert "validate_project" not in memory.get_memory_snapshot()["skills"]
