from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional
import numpy as np


@dataclass(frozen=True)
class Pose:
    # World pose: position (x,y,z) and quaternion (x,y,z,w)
    p: tuple[float, float, float]
    q: tuple[float, float, float, float]


@dataclass(frozen=True)
class AssetSpec:
    name: str
    usd_path: str
    semantic_label: Optional[str] = None
    scale: float = 1.0


@dataclass(frozen=True)
class SensorSpec:
    name: str
    type: str  # e.g., camera_rgb / depth / segmentation
    pose: Pose
    intrinsics: Dict[str, Any]


@dataclass(frozen=True)
class SceneSpec:
    usd_path: Optional[str] = None
    dome_light_intensity: float = 1500.0
    physics_dt: float = 1.0 / 60.0


@dataclass
class FrameBundle:
    rgb: Optional[np.ndarray] = None  # HWC uint8
    depth: Optional[np.ndarray] = None  # HW float32
    seg: Optional[np.ndarray] = None  # HW int32
    meta: Dict[str, Any] = None
