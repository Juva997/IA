import os
import sys
sys.path.append(os.getcwd())
from bootstrap.container import build_engine
from cognition.planner import Planner
from actions.registry import ActionRegistry
from core.llm_router import LLMRouter
from integrations.llm_client import LLMClient

engine = build_engine()
planner = engine.planner
print('router:', engine.router)

goal = 'crie um código python simples que funcione corretamente'
tools = planner._format_tools()
prompt = planner._build_prompt(goal, tools)
print('PROMPT:')
print(prompt)
response = planner.llm.generate(goal, prompt, None)
print('RESPONSE:')
print(response)
print('PARSE:')
plan = planner._parse(response, goal)
print(plan)
