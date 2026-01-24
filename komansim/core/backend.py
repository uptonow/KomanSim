from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Protocol, runtime_checkable

from .types import AssetSpec, FrameBundle, Pose, SceneSpec, SensorSpec


@runtime_checkable
class SimBackend(Protocol):
    """Backends (Isaac today, your engine tomorrow) implement this stable contract."""

    def start(self) -> None: ...
    def close(self) -> None: ...

    def reset(self, seed: Optional[int] = None) -> None: ...

    def load_scene(self, scene: SceneSpec) -> None: ...
    def spawn_asset(self, asset: AssetSpec, pose: Pose) -> str: ...
    def set_pose(self, handle: str, pose: Pose) -> None: ...

    def add_sensor(self, sensor: SensorSpec) -> str: ...

    def step(self, dt: float) -> None: ...
    def render(self) -> FrameBundle: ...


@dataclass(frozen=True)
class BackendInit:
    name: str
    headless: bool = True
    width: int = 1280
    height: int = 720
    extra: Dict[str, Any] | None = None
