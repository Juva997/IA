def test_async_eventbus_and_adapter():
    from service.eventbus.async_event_bus import AsyncEventBus, SyncEventBusAdapter

    events = []

    async def a_handler(data):
        events.append(("a", data))

    def s_handler(data):
        events.append(("s", data))

    bus = AsyncEventBus()
    bus.on("test:event", a_handler)
    bus.on("test:event", s_handler)

    import asyncio

    # emitir de forma assíncrona e verificar handlers
    asyncio.run(bus.emit("test:event", {"x": 1}))

    assert ("a", {"x": 1}) in events
    assert ("s", {"x": 1}) in events

    # Adapter síncrono deve funcionar mesmo sem loop
    adapter = SyncEventBusAdapter(bus)
    adapter.emit("test:event", {"y": 2})

    # asyncio.run ou execução síncrona terminará quando handlers concluírem
    import time

    time.sleep(0.01)

    assert ("a", {"y": 2}) in events
    assert ("s", {"y": 2}) in events


def test_executor_worker_invokes_tool_and_emits_event():
    import asyncio

    from service.executor.worker import ExecutorWorker
    from service.tools.mcp_adapter import ToolCatalog, MCPTool
    from service.eventbus.async_event_bus import AsyncEventBus

    async def run_test():
        q = asyncio.Queue()

        catalog = ToolCatalog()

        class Dummy(MCPTool):
            def invoke(self, payload, timeout=30):
                return {"status": "success", "output": payload}

        catalog.register(Dummy("echo", "http://example"))

        bus = AsyncEventBus()
        events = []

        async def on_step(data):
            events.append(data)

        bus.on("step_executed", on_step)

        worker = ExecutorWorker(q, catalog, event_bus=bus)
        task = asyncio.create_task(worker.run())

        await q.put({"action": "echo", "data": {"hello": "worker"}})
        await q.join()

        # aguardar handlers async concluírem
        await asyncio.sleep(0.01)

        assert events and events[0]["step"]["action"] == "echo"

        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            # esperado: worker foi cancelado enquanto aguardava novas tarefas
            pass
        except Exception:
            pass

    asyncio.run(run_test())
