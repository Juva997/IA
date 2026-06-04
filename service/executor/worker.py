"""Executor worker assíncrono protótipo.

Consome tarefas de uma `asyncio.Queue`, invoca ferramentas via `ToolCatalog`
e emite eventos para o `AsyncEventBus`.
"""
import asyncio
import logging
from typing import Any, Optional

from service.tools.mcp_adapter import ToolCatalog
from service.eventbus.async_event_bus import AsyncEventBus

logger = logging.getLogger(__name__)


class ExecutorWorker:
    def __init__(self, task_queue: asyncio.Queue, catalog: ToolCatalog, critic=None, event_bus: Optional[AsyncEventBus] = None, max_retries: int = 2):
        self.task_queue = task_queue
        self.catalog = catalog
        self.critic = critic
        self.event_bus = event_bus
        self.max_retries = max_retries

    async def run(self):
        while True:
            task = await self.task_queue.get()
            try:
                result = await self._execute_task(task)
                feedback = self._evaluate(result)
                if self.event_bus:
                    await self.event_bus.emit("step_executed", {"step": task, "result": result, "feedback": feedback})
            finally:
                self.task_queue.task_done()

    async def _execute_task(self, task: dict) -> dict:
        action = task.get("action")
        tool = self.catalog.get(action)
        if not tool:
            return {"status": "error", "error": "tool_not_found"}

        data = task.get("data", {})
        try:
            res = tool.invoke(data)
            if asyncio.iscoroutine(res):
                res = await res
            return res if isinstance(res, dict) else {"status": "success", "output": res}
        except Exception as e:
            logger.exception("task invoke failed")
            return {"status": "error", "error": str(e)}

    def _evaluate(self, result: dict) -> str:
        if self.critic and hasattr(self.critic, "evaluate"):
            return self.critic.evaluate(result)
        return "success" if result.get("status") == "success" else "fail"


if __name__ == "__main__":
    # demo rápido: registra um tool dummy e executa uma tarefa
    async def demo():
        q = asyncio.Queue()
        from service.tools.mcp_adapter import ToolCatalog, MCPTool

        cat = ToolCatalog()

        class DummyTool(MCPTool):
            def invoke(self, payload, timeout=30):
                return {"status": "success", "output": payload}

        cat.register(DummyTool("echo", "http://example.local/echo"))
        bus = AsyncEventBus()
        worker = ExecutorWorker(q, cat, event_bus=bus)

        async def on_step(data):
            print("STEP EXECUTED:", data)

        bus.on("step_executed", on_step)

        await q.put({"action": "echo", "data": {"hello": "world"}})
        asyncio.create_task(worker.run())
        await asyncio.sleep(0.5)

    asyncio.run(demo())
