from cognition.planner import Planner


class DummyRegistry:
    def list_tools(self):
        return {}

    def get(self, action):
        return True


def test_parse_trailing_commas_and_python_literals():
    p = Planner(None, DummyRegistry())
    # LLM output with trailing commas and Python literals
    response = '''```json
    [
        {action: write_file, data: {path: 'out.txt', content: 'hello',},},
    ]
    ```'''
    result = p._parse(response, goal="gerar arquivo")
    assert isinstance(result, list)
    assert result[0]["action"] == "write_file"
    assert result[0]["data"]["path"] == "out.txt"
    assert result[0]["data"]["content"] == "hello"


def test_parse_none_true_false_and_unquoted_values():
    p = Planner(None, DummyRegistry())
    response = "[{'action': write_file, 'data': {'path': file.txt, 'content': None, 'flag': True}}]"
    res = p._parse(response, goal="teste")
    assert isinstance(res, list)
    assert res[0]["action"] == "write_file"
    assert res[0]["data"]["path"] == "file.txt"
    # None should be converted to null -> parsed as None in Python json
    assert res[0]["data"].get("content") is None
