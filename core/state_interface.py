from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class IStateManager(ABC):
    """Interface mínima para adaptação do gerenciador de estado.

    Objetivo: permitir troca pluggable do backend de estado (memória, Redis, etc.)
    mantendo a compatibilidade com a API usada pelo código existente.
    """

    @abstractmethod
    def create_task(self, task_id: Optional[str] = None, goal: Optional[str] = None, token_budget: Optional[int] = None) -> str:
        raise NotImplementedError()

    @abstractmethod
    def close_task(self, task_id: str) -> None:
        raise NotImplementedError()

    @abstractmethod
    def get_task_state(self, task_id: str) -> Any:
        raise NotImplementedError()

    @abstractmethod
    def update_task(self, task_id: str, **kwargs) -> None:
        raise NotImplementedError()

    @abstractmethod
    def update_session(self, **kwargs) -> None:
        raise NotImplementedError()

    @abstractmethod
    def set_session_budget(self, budget: Optional[int]) -> None:
        raise NotImplementedError()

    @abstractmethod
    def export_state(self) -> Dict[str, Any]:
        raise NotImplementedError()

    @abstractmethod
    def import_state(self, state: Dict[str, Any]) -> None:
        raise NotImplementedError()

    @abstractmethod
    def pretty_print(self) -> str:
        raise NotImplementedError()
