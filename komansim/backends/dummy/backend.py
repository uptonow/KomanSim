from __future__ import annotations
import numpy as np

from komansim.core.registry import register_backend
from komansim.core.types import AssetSpec, FrameBundle, Pose, SceneSpec, SensorSpec


class DummyBackend:
    """A no-dependency backend to validate the platform pipeline."""

    def __init__(self, headless=True, width=640, height=480, **kwargs):
        self.w = int(width)
        self.h = int(height)
        self._assets = []
        self._frame_count = 0

    def start(self) -> None:
        return None

    def close(self) -> None:
        return None

    def reset(self, seed=None) -> None:
        self._assets = []
        self._frame_count = 0
        return None

    def load_scene(self, scene: SceneSpec) -> None:
        return None

    def spawn_asset(self, asset: AssetSpec, pose: Pose) -> str:
        self._assets.append(asset)
        return asset.name

    def set_pose(self, handle: str, pose: Pose) -> None:
        return None

    def add_sensor(self, sensor: SensorSpec) -> str:
        return sensor.name

    def step(self, dt: float) -> None:
        return None

    def render(self) -> FrameBundle:
        rgb = np.zeros((self.h, self.w, 3), dtype=np.uint8)
        seg = None

        if self._assets:
            seg = np.zeros((self.h, self.w), dtype=np.int32)
            # Draw a box for each asset
            # Use asset index + 1 as instance_id/class_id
            for i, asset in enumerate(self._assets):
                instance_id = i + 1
                # Simple bouncing box logic based on frame count
                box_size = 50
                x = (self._frame_count * 10 + i * 100) % (self.w - box_size)
                y = (self._frame_count * 5 + i * 50) % (self.h - box_size)

                seg[y : y + box_size, x : x + box_size] = instance_id

        self._frame_count += 1
        return FrameBundle(rgb=rgb, depth=None, seg=seg, meta={"backend": "dummy"})


register_backend("dummy", DummyBackend)
