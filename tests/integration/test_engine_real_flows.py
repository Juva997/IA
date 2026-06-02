from unittest.mock import Mock

from actions.executor import Executor
from actions.registry import ActionRegistry
from bootstrap.container import build_engine
from cognition.agent import Agent
from cognition.critic import Critic
from core.engine import AutonomousEngine
from memory.memory import Memory
from security.security import SecurityManager
from tests.conftest import FakeLLM, FakeRetriever, FakeVectorStore


def test_engine_runs_real_file_plan_in_isolated_workspace(deterministic_engine):
    result = deterministic_engine.run(
        "crie uma pasta chamada projeto, dentro crie arquivo resultado.txt "
        "com ok e depois leia"
    )

    assert result["status"] == "success"
    assert result["output"] == "ok"
    assert deterministic_engine.session_context["last_folder_path"] == "projeto"
    assert deterministic_engine.session_context["last_file_path"] == (
        "projeto/resultado.txt"
    )


def test_engine_memory_statement_then_question_without_llm(deterministic_engine, fake_llm):
    stored = deterministic_engine.run("me chamo Ana")
    recalled = deterministic_engine.run("qual e o meu nome?")

    assert stored["status"] == "success"
    assert recalled["status"] == "success"
    assert "Ana" in recalled["output"]
    assert fake_llm.calls == []


def test_engine_direct_question_uses_injected_fake_llm(isolated_workspace):
    llm = FakeLLM("resposta sem rede")
    engine = build_engine(
        llm_router=llm,
        persist_path=str(isolated_workspace / "memory"),
        safe_root=str(isolated_workspace),
        debug=False,
        enable_router=False,
    )

    result = engine.run("explique algo que nao tenha resposta local")

    assert result == {"status": "success", "output": "resposta sem rede"}
    assert len(llm.calls) == 1


def test_engine_blocks_unsafe_step_before_real_executor(isolated_workspace):
    registry = ActionRegistry()
    registry.auto_register()
    planner = Mock()
    planner.create_plan.return_value = [
        {"action": "write_file", "data": {"path": "../escape.txt", "content": "x"}}
    ]
    planner.classify_goal.return_value = "action"
    memory = Memory(
        FakeVectorStore(),
        FakeRetriever(),
        persist_path=str(isolated_workspace / "memory"),
    )
    engine = AutonomousEngine(
        agent=Agent(FakeLLM()),
        planner=planner,
        memory=memory,
        executor=Executor(registry),
        critic=Critic(),
        guard=SecurityManager(safe_root=str(isolated_workspace)),
        debug=False,
    )

    result = engine.run("crie arquivo fora")

    assert result["status"] == "error"
    assert result["error"].startswith("security_blocked:")
    assert not (isolated_workspace.parent / "escape.txt").exists()
