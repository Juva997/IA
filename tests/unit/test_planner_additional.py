from cognition.planner import Planner


class DummyRegistry:
    def list_tools(self):
        return {}

    def get(self, action):
        return True


def test_plan_write_file_strips_content_keyword():
    p = Planner(None, DummyRegistry())
    text = "Crie um arquivo chamado 'resumo.txt' com conteúdo: 'isto é um teste e depois leia o arquivo'"
    plan = p._plan_write_file(text, text.lower(), session={})
    assert plan is not None and isinstance(plan, list)
    step = plan[0]
    assert step["action"] == "write_file"
    assert step["data"]["path"] == "resumo.txt"
    assert "isto é um teste" in step["data"]["content"]
    assert "leia" not in step["data"]["content"]


def test_plan_write_file_session_prefix():
    p = Planner(None, DummyRegistry())
    text = "Crie um arquivo chamado 'teste.txt' dentro desta pasta com conteúdo 'abc'"
    plan = p._plan_write_file(text, text.lower(), session={"last_folder_path": "sessao/pasta"})
    assert plan is not None and isinstance(plan, list)
    step = plan[0]
    assert step["data"]["path"] == "sessao/pasta/teste.txt"


def test_parse_repairs_single_quotes_and_codeblock():
    p = Planner(None, DummyRegistry())
    response = "Aqui está o plano:\n```json\n[{'action':'write_file','data':{'path':'a.txt','content':'hello'}}]\n```"
    result = p._parse(response, goal="alguma coisa")
    assert isinstance(result, list)
    assert result[0]["action"] == "write_file"
    assert result[0]["data"]["path"] == "a.txt"
    assert result[0]["data"]["content"] == "hello"


def test_repair_skips_run_python_when_file_missing():
    p = Planner(None, DummyRegistry())
    steps = [{"action": "run_python", "data": {"code": "exec(open('missing.py').read())"}}]
    final = p._repair_plan_steps(steps)
    assert final == []


def test_repair_generates_unittest_for_goal():
    p = Planner(None, DummyRegistry())
    final = p._repair_plan_steps([], goal="por favor execute teste unit")
    assert len(final) == 2
    assert final[0]["action"] == "write_file"
    assert "teste_unitario.py" in final[0]["data"]["path"]
