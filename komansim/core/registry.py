from __future__ import annotations
from typing import Dict, Type, Any
from .backend import SimBackend

_BACKENDS: Dict[str, Type[SimBackend]] = {}


def register_backend(name: str, cls: Type[SimBackend]) -> None:
    _BACKENDS[name] = cls


def make_backend(name: str, **kwargs: Any) -> SimBackend:
    if name not in _BACKENDS:
        raise KeyError(f"Backend '{name}' not registered. Available: {list(_BACKENDS)}")
    return _BACKENDS[name](**kwargs)
