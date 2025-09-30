from __future__ import annotations

from typing import Any, Callable, Dict, Type, TypeVar

from datainsight_agent.core.interfaces import ServiceInterface


T = TypeVar("T", bound=ServiceInterface)


class ServiceContainer:
    """Lightweight dependency injection container.

    - Register concrete instances via register()
    - Register factories via register_factory()
    - Resolve services via get()
    """

    def __init__(self) -> None:
        self._instances: Dict[Type[ServiceInterface], ServiceInterface] = {}
        self._factories: Dict[Type[ServiceInterface], Callable[[], ServiceInterface]] = {}

    def register(self, service_type: Type[T], instance: T) -> None:
        self._instances[service_type] = instance

    def register_factory(self, service_type: Type[T], factory: Callable[[], T]) -> None:
        self._factories[service_type] = factory  # type: ignore[assignment]

    def get(self, service_type: Type[T]) -> T:
        inst = self._instances.get(service_type)
        if inst is not None:
            return inst  # type: ignore[return-value]
        factory = self._factories.get(service_type)
        if factory is None:
            raise KeyError(f"Service not registered: {service_type}")
        created = factory()
        self._instances[service_type] = created
        return created  # type: ignore[return-value]


