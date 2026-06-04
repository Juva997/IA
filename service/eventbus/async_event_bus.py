"""Prototipo: EventBus assíncrono com adaptador síncrono de compatibilidade.

Uso:
 - `AsyncEventBus` para emissões/handlers async
 - `SyncEventBusAdapter` para compatibilidade com código existente
"""
import asyncio
import inspect
import logging
from typing import Any, Callable, Dict, List

logger = logging.getLogger(__name__)


class AsyncEventBus:
    def __init__(self):
        self._subs: Dict[str, List[Callable[[Any], Any]]] = {}

    def on(self, event: str, handler: Callable[[Any], Any]):
        """Registra um handler (sync ou async) para um evento."""
        self._subs.setdefault(event, []).append(handler)

    def off(self, event: str, handler: Callable[[Any], Any]):
        if event in self._subs and handler in self._subs[event]:
            self._subs[event].remove(handler)

    async def emit(self, event: str, data: Any):
        """Emite o evento de forma assíncrona; não propaga exceções de handlers."""
        handlers = list(self._subs.get(event, []))
        if not handlers:
            return

        loop = asyncio.get_running_loop()
        tasks = []
        for h in handlers:
            try:
                res = h(data)
                if inspect.isawaitable(res):
                    tasks.append(res)
                else:
                    # handler síncrono: executar no threadpool para não bloquear
                    tasks.append(loop.run_in_executor(None, lambda r=res: r))
            except Exception:
                logger.exception("event handler raised")

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)


class SyncEventBusAdapter:
    """Adapter simples para permitir chamadas `emit` síncronas em código legado.

    Observação: se não houver loop rodando, `emit` vai criar um loop temporário.
    """

    def __init__(self, async_bus: AsyncEventBus):
        self.async_bus = async_bus

    def on(self, event: str, handler: Callable[[Any], Any]):
        self.async_bus.on(event, handler)

    def emit(self, event: str, data: Any):
        try:
            loop = asyncio.get_running_loop()
            # agenda e retorna imediatamente
            asyncio.create_task(self.async_bus.emit(event, data))
        except RuntimeError:
            # sem loop rodando: cria um loop temporário
            asyncio.run(self.async_bus.emit(event, data))


def create_compat_eventbus() -> SyncEventBusAdapter:
    bus = AsyncEventBus()
    return SyncEventBusAdapter(bus)


__all__ = ["AsyncEventBus", "SyncEventBusAdapter", "create_compat_eventbus"]
