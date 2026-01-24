from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, Optional
import numpy as np

from komansim.core.registry import register_backend
from komansim.core.types import AssetSpec, FrameBundle, Pose, SceneSpec, SensorSpec


@dataclass
class _PyBulletState:
    """Internal state for PyBullet backend."""

    client_id: Optional[int] = None
    pybullet_version: str = "unknown"


@dataclass
class _ObjectInfo:
    """Information about a spawned object."""

    body_unique_id: int
    instance_id: int  # For segmentation (1-based, 0 is background)


class PyBulletBackend:
    """PyBullet backend for synthetic data generation.

    PyBullet uses DIRECT mode by default (headless-friendly in WSL).
    This backend:
    - Creates or loads scenes with physics
    - Manages PyBullet physics simulation
    - Renders RGB, depth, and segmentation images using getCameraImage
    - Supports camera sensors with intrinsics
    - Uses TinyRenderer for headless rendering
    """

    def __init__(self, headless=True, width=1280, height=720, **kwargs):
        self.headless = bool(headless)
        self.w = int(width)
        self.h = int(height)
        self.extra = kwargs
        self._st = _PyBulletState()
        self._handles: Dict[str, _ObjectInfo] = {}  # asset name -> ObjectInfo
        self._sensors: Dict[str, Dict[str, Any]] = {}  # sensor name -> sensor config
        self._next_instance_id: int = 1  # Start at 1 (0 is background)
        self._pybullet = None  # Will be set in start()

    def start(self) -> None:
        """Initialize PyBullet library and connect to physics server."""
        try:
            import pybullet as pb
        except ImportError as e:
            raise RuntimeError(
                "PyBullet backend requires 'pybullet' package. Install with: pip install pybullet"
            ) from e

        self._pybullet = pb
        self._st.pybullet_version = getattr(pb, "__version__", "unknown")

        # Connect to physics server in DIRECT mode (headless-friendly)
        if self._st.client_id is None:
            self._st.client_id = self._pybullet.connect(self._pybullet.DIRECT)

    def close(self) -> None:
        """Clean up PyBullet resources."""
        if self._st.client_id is not None:
            self._pybullet.disconnect(self._st.client_id)
            self._st.client_id = None

    def reset(self, seed: Optional[int] = None) -> None:
        """Reset simulation state and optionally set random seed."""
        if self._st.client_id is None:
            return

        # Reset simulation (clears all objects)
        self._pybullet.resetSimulation(physicsClientId=self._st.client_id)

        # Clear handles since all objects are removed
        self._handles.clear()
        self._next_instance_id = 1

        if seed is not None:
            # Set random seed for PyBullet
            import random

            random.seed(seed)
            np.random.seed(seed)

    def load_scene(self, scene: SceneSpec) -> None:
        """Load or create scene from SceneSpec.

        Creates a ground plane and sets physics parameters.
        """
        if self._st.client_id is None:
            self.start()

        # Reset simulation (clears all objects)
        self._pybullet.resetSimulation(physicsClientId=self._st.client_id)

        # Clear handles since all objects are removed
        self._handles.clear()
        self._next_instance_id = 1

        # Set gravity (default is -9.8 m/s^2 in Z)
        self._pybullet.setGravity(0, 0, -9.8, physicsClientId=self._st.client_id)

        # Set timestep
        self._pybullet.setTimeStep(scene.physics_dt, physicsClientId=self._st.client_id)

        # Load ground plane
        # Try to use pybullet_data if available (included with pybullet package)
        try:
            import pybullet_data

            plane_path = os.path.join(pybullet_data.getDataPath(), "plane.urdf")
            if os.path.exists(plane_path):
                self._pybullet.loadURDF(plane_path, physicsClientId=self._st.client_id)
            else:
                # Fallback: create a static box as ground
                self._create_ground_plane()
        except (ImportError, AttributeError):
            # Fallback: create a static box as ground
            self._create_ground_plane()

    def _create_ground_plane(self) -> None:
        """Create a static box as ground plane."""
        # Create a large flat box as ground
        ground_shape = self._pybullet.createCollisionShape(
            self._pybullet.GEOM_BOX, halfExtents=[10, 10, 0.1], physicsClientId=self._st.client_id
        )
        self._pybullet.createMultiBody(
            baseMass=0,  # Static
            baseCollisionShapeIndex=ground_shape,
            basePosition=[0, 0, -0.1],
            physicsClientId=self._st.client_id,
        )

    def spawn_asset(self, asset: AssetSpec, pose: Pose) -> str:
        """Spawn an asset into the scene.

        Supports primitive://box and primitive://sphere.
        For other assets, falls back to a box using asset.scale.
        Returns a handle (asset name) for later reference.
        """
        if self._st.client_id is None:
            raise RuntimeError("Backend not started. Call start() first.")

        # Determine geometry type
        if asset.usd_path and asset.usd_path.startswith("primitive://"):
            primitive_type = asset.usd_path.replace("primitive://", "")
            if primitive_type == "box":
                geom_type = self._pybullet.GEOM_BOX
                # Default size
                half_extents = [0.1 * asset.scale, 0.1 * asset.scale, 0.1 * asset.scale]
            elif primitive_type == "sphere":
                geom_type = self._pybullet.GEOM_SPHERE
                radius = 0.1 * asset.scale
            else:
                # Unknown primitive, fallback to box
                geom_type = self._pybullet.GEOM_BOX
                half_extents = [0.1 * asset.scale, 0.1 * asset.scale, 0.1 * asset.scale]
        else:
            # Fallback to box for non-primitive assets or None usd_path
            geom_type = self._pybullet.GEOM_BOX
            half_extents = [0.1 * asset.scale, 0.1 * asset.scale, 0.1 * asset.scale]

        # Create collision and visual shapes
        if geom_type == self._pybullet.GEOM_BOX:
            collision_shape = self._pybullet.createCollisionShape(
                geom_type, halfExtents=half_extents, physicsClientId=self._st.client_id
            )
            visual_shape = self._pybullet.createVisualShape(
                geom_type,
                halfExtents=half_extents,
                rgbaColor=[0.8, 0.2, 0.2, 1.0],  # Red color for visibility
                physicsClientId=self._st.client_id,
            )
        elif geom_type == self._pybullet.GEOM_SPHERE:
            collision_shape = self._pybullet.createCollisionShape(
                geom_type, radius=radius, physicsClientId=self._st.client_id
            )
            visual_shape = self._pybullet.createVisualShape(
                geom_type,
                radius=radius,
                rgbaColor=[0.2, 0.8, 0.2, 1.0],  # Green color for visibility
                physicsClientId=self._st.client_id,
            )
        else:
            # Fallback to box
            collision_shape = self._pybullet.createCollisionShape(
                self._pybullet.GEOM_BOX,
                halfExtents=half_extents,
                physicsClientId=self._st.client_id,
            )
            visual_shape = self._pybullet.createVisualShape(
                self._pybullet.GEOM_BOX,
                halfExtents=half_extents,
                rgbaColor=[0.8, 0.2, 0.2, 1.0],
                physicsClientId=self._st.client_id,
            )

        # Create multi-body with initial pose
        # Convert quaternion from (x,y,z,w) to PyBullet format (x,y,z,w) - same order
        body_unique_id = self._pybullet.createMultiBody(
            baseMass=1.0,  # 1 kg
            baseCollisionShapeIndex=collision_shape,
            baseVisualShapeIndex=visual_shape,
            basePosition=list(pose.p),
            baseOrientation=list(pose.q),
            physicsClientId=self._st.client_id,
        )

        # Store handle with instance ID for segmentation
        instance_id = self._next_instance_id
        self._next_instance_id += 1

        self._handles[asset.name] = _ObjectInfo(
            body_unique_id=body_unique_id, instance_id=instance_id
        )

        return asset.name

    def set_pose(self, handle: str, pose: Pose) -> None:
        """Set the pose of an asset by handle."""
        if handle not in self._handles:
            return

        if self._st.client_id is None:
            return

        obj_info = self._handles[handle]
        body_id = obj_info.body_unique_id

        # Reset base position and orientation
        self._pybullet.resetBasePositionAndOrientation(
            body_id, list(pose.p), list(pose.q), physicsClientId=self._st.client_id
        )

    def add_sensor(self, sensor: SensorSpec) -> str:
        """Add a camera sensor to the scene.

        Stores sensor configuration for use during rendering.
        """
        # Store sensor config
        self._sensors[sensor.name] = {
            "pose": sensor.pose,
            "intrinsics": sensor.intrinsics,
            "type": sensor.type,
        }
        return sensor.name

    def step(self, dt: float) -> None:
        """Step the physics simulation."""
        if self._st.client_id is None:
            return

        # PyBullet uses fixed timestep, but we can step multiple times
        # Get current timestep
        current_dt = self._pybullet.getPhysicsEngineParameters(physicsClientId=self._st.client_id)[
            "fixedTimeStep"
        ]
        num_steps = max(1, int(dt / current_dt))
        for _ in range(num_steps):
            self._pybullet.stepSimulation(physicsClientId=self._st.client_id)

    def render(self) -> FrameBundle:
        """Render the current scene and return FrameBundle.

        Renders RGB, depth, and segmentation using getCameraImage.
        """
        if self._st.client_id is None:
            rgb = np.zeros((self.h, self.w, 3), dtype=np.uint8)
            return FrameBundle(
                rgb=rgb,
                depth=None,
                seg=None,
                meta={"backend": "pybullet", "note": "not initialized"},
            )

        # Get camera from first sensor (or use default)
        camera_pos = None
        target_pos = [0, 0, 0]  # Default look at origin
        intrinsics = None

        if self._sensors:
            sensor_name = list(self._sensors.keys())[0]
            sensor_cfg = self._sensors[sensor_name]
            pose = sensor_cfg["pose"]
            camera_pos = np.array(pose.p)
            # For MVP, compute target from camera pose (look toward origin)
            target_pos = [0, 0, 0]
            intrinsics = sensor_cfg.get("intrinsics", {})
        else:
            # Default camera
            camera_pos = np.array([2.0, 2.0, 1.5])
            target_pos = [0, 0, 0]

        # Compute view matrix
        # PyBullet's getCameraImage expects camera position, target, and up vector
        up_vector = [0, 0, 1]  # Z-up

        # Compute projection matrix from intrinsics if provided
        # Otherwise use default FOV=60
        if intrinsics:
            fx = intrinsics.get("fx", self.w / 2.0)
            _fy = intrinsics.get("fy", self.h / 2.0)  # TODO: use in projection matrix
            _cx = intrinsics.get("cx", self.w / 2.0)  # TODO: use in projection matrix
            _cy = intrinsics.get("cy", self.h / 2.0)  # TODO: use in projection matrix

            # Convert intrinsics to projection matrix
            # For perspective projection: near=0.01, far=10.0
            near = 0.01
            far = 10.0

            # Projection matrix from intrinsics
            # Using simplified projection (PyBullet uses FOV internally)
            # Approximate FOV from fx: FOV = 2 * atan(width / (2 * fx))
            fov = 2 * np.arctan(self.w / (2 * fx)) * 180 / np.pi
        else:
            fov = 60.0
            near = 0.01
            far = 10.0

        # Render using getCameraImage
        # Flags: ER_SEGMENTATION_MASK_OBJECT_AND_LINKINDEX for segmentation
        view_matrix = self._pybullet.computeViewMatrix(
            cameraEyePosition=list(camera_pos),
            cameraTargetPosition=list(target_pos),
            cameraUpVector=up_vector,
        )

        projection_matrix = self._pybullet.computeProjectionMatrixFOV(
            fov=fov, aspect=self.w / self.h, nearVal=near, farVal=far
        )

        # Get camera image with segmentation
        # ER_TINY_RENDERER = 1, ER_SEGMENTATION_MASK_OBJECT_AND_LINKINDEX = 2
        # Access constants safely (they're module-level attributes)
        renderer = getattr(self._pybullet, "ER_TINY_RENDERER", 1)  # Default to 1 if not found
        flags = getattr(
            self._pybullet, "ER_SEGMENTATION_MASK_OBJECT_AND_LINKINDEX", 2
        )  # Default to 2 if not found

        width, height, rgb_img, depth_img, seg_img = self._pybullet.getCameraImage(
            width=self.w,
            height=self.h,
            viewMatrix=view_matrix,
            projectionMatrix=projection_matrix,
            renderer=renderer,
            flags=flags,
            physicsClientId=self._st.client_id,
        )

        # Convert RGB: PyBullet returns list/tuple, convert to numpy array first
        # Then reshape from flat array to (height, width, 4) if needed
        rgb_img = np.array(rgb_img, dtype=np.uint8)
        if rgb_img.ndim == 1:
            rgb_reshaped = np.reshape(rgb_img, (height, width, 4))
        else:
            rgb_reshaped = rgb_img
        rgb = rgb_reshaped[:, :, :3].astype(np.uint8)  # Remove alpha channel, keep RGB

        # Convert depth: PyBullet returns list/tuple, convert to numpy array first
        # Then reshape from flat array to (height, width) if needed
        depth_buffer_flat = np.array(depth_img, dtype=np.float32)
        if depth_buffer_flat.ndim == 1:
            depth_buffer = np.reshape(depth_buffer_flat, (height, width))
        else:
            depth_buffer = depth_buffer_flat
        # Avoid division by zero: clamp depth_buffer to [epsilon, 1-epsilon]
        epsilon = 1e-6
        depth_buffer_clamped = np.clip(depth_buffer, epsilon, 1.0 - epsilon)
        depth = far * near / (far - (far - near) * depth_buffer_clamped)
        depth = depth.astype(np.float32)

        # Convert segmentation: PyBullet returns list/tuple, convert to numpy array first
        # Then reshape from flat array to (height, width) if needed
        seg_raw_flat = np.array(seg_img, dtype=np.int32)
        if seg_raw_flat.ndim == 1:
            seg_raw = np.reshape(seg_raw_flat, (height, width))
        else:
            seg_raw = seg_raw_flat
        # Decode: objectUniqueId = seg_raw & ((1<<24)-1)
        object_unique_id = seg_raw & ((1 << 24) - 1)

        # Map objectUniqueId -> instance_id using our mapping
        # Background (0 or -1) maps to 0
        seg = np.zeros_like(object_unique_id, dtype=np.int32)

        # Create reverse mapping: body_unique_id -> instance_id
        body_to_instance = {
            obj_info.body_unique_id: obj_info.instance_id for obj_info in self._handles.values()
        }

        # Map each unique object ID to instance ID
        for body_id, instance_id in body_to_instance.items():
            seg[object_unique_id == body_id] = instance_id

        # Background (0 or -1) remains 0 (already initialized to 0)
        # Also handle invalid IDs (negative values that don't match any body)
        seg[object_unique_id < 0] = 0

        # Build metadata
        meta = {
            "backend": "pybullet",
            "backend_version": self._st.pybullet_version,
            "width": self.w,
            "height": self.h,
            "seg_encoding": "instance_id int32 (0=background, 1..K=instances)",
            "depth_encoding": "metric float32 (meters)",
        }

        return FrameBundle(rgb=rgb, depth=depth, seg=seg, meta=meta)


register_backend("pybullet", PyBulletBackend)
