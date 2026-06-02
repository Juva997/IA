from unittest.mock import Mock

import pytest

from actions.registry import ActionRegistry
from cognition.agent import Agent
from cognition.planner import Planner
from core.engine import AutonomousEngine
from memory.memory import Memory


def simple_embedding(text, size=384):
    vec = [float(ord(c)) for c in text[:size]]
    if len(vec) < size:
        vec += [0.0] * (size - len(vec))
    return vec


@pytest.fixture
def mock_llm():
    llm = Mock()
    llm.generate.return_value = "Resposta simulada"
    return llm


@pytest.fixture
def mock_planner():
    planner = Mock()
    planner.create_plan.return_value = [
        {"action": "write_file", "data": {"path": "test.txt", "content": "oi"}}
    ]
    return planner


@pytest.fixture
def mock_memory():
    memory = Mock()
    memory.build_context.return_value = {
        "goal": "teste",
        "recent_history": [],
        "retrieved_memory": [],
        "facts": {},
    }
    return memory


@pytest.fixture
def mock_executor():
    executor = Mock()
    executor.execute.return_value = {"status": "success", "output": "Executado"}
    return executor


@pytest.fixture
def mock_critic():
    critic = Mock()
    critic.evaluate.return_value = {"score": 8, "feedback": "Bom"}
    return critic


def test_engine_run_simple_chat(
    mock_llm, mock_planner, mock_memory, mock_executor, mock_critic
):
    agent = Agent(mock_llm)
    engine = AutonomousEngine(
        agent=agent,
        planner=mock_planner,
        memory=mock_memory,
        executor=mock_executor,
        critic=mock_critic,
        max_iterations=1,
    )

    result = engine.run("oi")

    assert "output" in result
    assert result["output"].startswith("Olá")
    mock_llm.generate.assert_not_called()


def test_engine_run_action_plan(
    mock_llm, mock_planner, mock_memory, mock_executor, mock_critic
):
    mock_planner.create_plan.return_value = [
        {"action": "write_file", "data": {"path": "test.txt", "content": "oi"}}
    ]
    agent = Agent(mock_llm)
    engine = AutonomousEngine(
        agent=agent,
        planner=mock_planner,
        memory=mock_memory,
        executor=mock_executor,
        critic=mock_critic,
        max_iterations=2,
    )

    result = engine.run("crie um arquivo teste.txt")

    assert "output" in result
    mock_executor.execute.assert_called()


def test_engine_updates_session_last_folder_path(
    mock_llm, mock_memory, mock_executor, mock_critic
):
    mock_planner = Mock()
    mock_planner.create_plan.return_value = [
        {"action": "create_folder", "data": {"path": "teste"}}
    ]
    mock_planner.classify_goal.return_value = "action"

    agent = Agent(mock_llm)
    engine = AutonomousEngine(
        agent=agent,
        planner=mock_planner,
        memory=mock_memory,
        executor=mock_executor,
        critic=mock_critic,
        max_iterations=2,
    )

    result = engine.run("crie uma pasta chamada teste")

    assert result["status"] == "success"
    assert engine.session_context["last_folder_path"] == "teste"


def test_engine_memory_name_statement_then_question(
    mock_llm, mock_executor, mock_critic, tmp_path
):
    vector_store = Mock()
    vector_store.add = Mock()
    vector_store.save = Mock()
    vector_store.load = Mock()
    vector_store.clear = Mock()
    memory = Memory(vector_store, Mock(), persist_path=str(tmp_path / "memory"))
    planner = Mock()
    planner.create_plan.return_value = []
    planner.classify_goal.return_value = "question"

    agent = Agent(mock_llm)
    engine = AutonomousEngine(
        agent=agent,
        planner=planner,
        memory=memory,
        executor=mock_executor,
        critic=mock_critic,
        max_iterations=2,
    )

    result = engine.run("meu nome é juvenal")
    assert result["status"] == "success"
    assert result["output"] == "Memória atualizada: seu nome é juvenal."

    result = engine.run("qual é o meu nome?")
    assert result["status"] == "success"
    assert result["output"] == "Seu nome é juvenal."
    mock_llm.generate.assert_not_called()


def test_engine_memory_name_question_without_memory_does_not_call_llm(
    mock_llm, mock_executor, mock_critic, tmp_path
):
    vector_store = Mock()
    vector_store.add = Mock()
    vector_store.save = Mock()
    vector_store.load = Mock()
    vector_store.clear = Mock()
    memory = Memory(vector_store, Mock(), persist_path=str(tmp_path / "memory"))
    planner = Mock()
    planner.create_plan.return_value = []
    planner.classify_goal.return_value = "question"

    agent = Agent(mock_llm)
    engine = AutonomousEngine(
        agent=agent,
        planner=planner,
        memory=memory,
        executor=mock_executor,
        critic=mock_critic,
        max_iterations=2,
    )

    result = engine.run("qual é o meu nome?")
    assert result["status"] == "success"
    assert result["output"] == "Ainda não sei seu nome."
    mock_llm.generate.assert_not_called()


def test_planner_create_plan(mock_llm):
    registry = ActionRegistry()
    planner = Planner(mock_llm, registry)

    plan = planner.create_plan("crie arquivo", {})

    assert isinstance(plan, list)
    mock_llm.generate.assert_called()


def test_engine_executes_full_plan_steps(
    mock_llm, mock_memory, mock_executor, mock_critic
):
    mock_planner = Mock()
    mock_planner.create_plan.return_value = [
        {"action": "create_folder", "data": {"path": "teste"}},
        {
            "action": "write_file",
            "data": {"path": "teste/teste.txt", "content": "hello world"},
        },
    ]
    mock_planner.classify_goal.return_value = "action"

    agent = Agent(mock_llm)
    engine = AutonomousEngine(
        agent=agent,
        planner=mock_planner,
        memory=mock_memory,
        executor=mock_executor,
        critic=mock_critic,
        max_iterations=2,
    )

    result = engine.run("crie um arquivo teste.txt")

    assert result["status"] == "success"
    assert mock_executor.execute.call_count == 2


def test_engine_direct_response_handles_llm_error(
    mock_llm, mock_planner, mock_memory, mock_executor, mock_critic
):
    mock_llm.generate.return_value = "[LLM_ERROR] timeout_llm"
    mock_planner.classify_goal.return_value = "question"
    mock_planner.create_plan.return_value = []

    agent = Agent(mock_llm)
    engine = AutonomousEngine(
        agent=agent,
        planner=mock_planner,
        memory=mock_memory,
        executor=mock_executor,
        critic=mock_critic,
        max_iterations=2,
    )

    result = engine.run("isso é uma pergunta sobre timeout")

    assert result["status"] == "error"
    assert "timeout_llm" in result["error"]
