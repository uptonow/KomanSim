from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, Optional
import numpy as np
import xml.etree.ElementTree as ET

from komansim.core.registry import register_backend
from komansim.core.types import AssetSpec, FrameBundle, Pose, SceneSpec, SensorSpec


@dataclass
class _MuJoCoState:
    """Internal state for MuJoCo backend."""

    model: Any = None  # mjModel
    data: Any = None  # mjData
    renderer: Any = None  # mujoco.Renderer
    mujoco_version: str = "unknown"


@dataclass
class _ObjectInfo:
    """Information about a spawned object."""

    body_id: int
    geom_id: int
    instance_id: int  # For segmentation (1-based, 0 is background)


class MuJoCoBackend:
    """MuJoCo backend for synthetic data generation.

    MuJoCo uses MJCF (XML) format for models rather than USD.
    This backend:
    - Creates or loads MJCF models
    - Manages MuJoCo physics simulation
    - Renders RGB, depth, and segmentation images using mujoco.Renderer
    - Supports camera sensors with intrinsics
    - Uses EGL for headless rendering (fallback to osmesa)
    """

    def __init__(self, headless=True, width=1280, height=720, **kwargs):
        self.headless = bool(headless)
        self.w = int(width)
        self.h = int(height)
        self.extra = kwargs
        self._st = _MuJoCoState()
        self._handles: Dict[str, _ObjectInfo] = {}  # asset name -> ObjectInfo
        self._sensors: Dict[str, Dict[str, Any]] = {}  # sensor name -> sensor config
        self._model_xml: Optional[str] = None
        self._next_instance_id: int = 1  # Start at 1 (0 is background)
        self._mujoco = None  # Will be set in start()

        # Set MUJOCO_GL environment variable for headless rendering
        if headless:
            # Prefer EGL, fallback to osmesa
            if "MUJOCO_GL" not in os.environ:
                os.environ["MUJOCO_GL"] = "egl"

    def start(self) -> None:
        """Initialize MuJoCo library and create renderer context."""
        try:
            import mujoco
        except ImportError as e:
            raise RuntimeError(
                "MuJoCo backend requires 'mujoco' package. Install with: pip install mujoco"
            ) from e

        self._mujoco = mujoco
        self._st.mujoco_version = getattr(mujoco, "__version__", "unknown")

        # Create a minimal default model if none exists
        if self._model_xml is None:
            # Create a basic empty world
            self._model_xml = """
            <mujoco>
                <worldbody>
                    <light pos="0 0 3" dir="0 0 -1"/>
                    <geom name="floor" type="plane" size="10 10 0.1" rgba="0.8 0.8 0.8 1"/>
                </worldbody>
            </mujoco>
            """

        # Load model
        try:
            self._st.model = self._mujoco.MjModel.from_xml_string(self._model_xml)
        except Exception as e:
            raise RuntimeError(f"Failed to load MuJoCo model: {e}") from e

        self._st.data = self._mujoco.MjData(self._st.model)

        # Create offscreen renderer
        try:
            self._st.renderer = self._mujoco.Renderer(self._st.model, height=self.h, width=self.w)
        except Exception as e:
            raise RuntimeError(
                f"Failed to create MuJoCo renderer. "
                f"Make sure MUJOCO_GL is set (egl or osmesa) and required libraries are installed. "
                f"Error: {e}"
            ) from e

    def close(self) -> None:
        """Clean up MuJoCo resources."""
        if self._st.renderer is not None:
            self._st.renderer = None
        if self._st.data is not None:
            self._st.data = None
        if self._st.model is not None:
            self._st.model = None

    def reset(self, seed: Optional[int] = None) -> None:
        """Reset simulation state and optionally set random seed."""
        if self._st.data is None:
            return

        self._mujoco.mj_resetData(self._st.model, self._st.data)

        if seed is not None:
            # Set random seed for MuJoCo
            np.random.seed(seed)
            # MuJoCo's RNG is reset by mj_resetData, but we can set qpos/qvel if needed

    def load_scene(self, scene: SceneSpec) -> None:
        """Load or create scene from SceneSpec.

        If scene.usd_path is provided, it should point to an MJCF XML file.
        Otherwise, creates a default scene.
        """
        if scene.usd_path:
            # For MuJoCo, usd_path should actually be an MJCF XML file path
            try:
                with open(scene.usd_path, "r") as f:
                    self._model_xml = f.read()
            except Exception as e:
                raise RuntimeError(f"Failed to load MJCF file from {scene.usd_path}: {e}") from e
        else:
            # Create default scene with lighting
            intensity = scene.dome_light_intensity / 1000.0  # Normalize
            self._model_xml = f"""
            <mujoco>
                <option timestep="{scene.physics_dt}"/>
                <worldbody>
                    <light name="dome" pos="0 0 5" dir="0 0 -1" diffuse="{intensity} {intensity} {intensity}"/>
                    <geom name="floor" type="plane" size="10 10 0.1" rgba="0.9 0.9 0.9 1"/>
                </worldbody>
            </mujoco>
            """

        # Reload model if already started
        if self._st.model is not None:
            # Parse XML and add any spawned objects back
            root = ET.fromstring(self._model_xml)
            worldbody = root.find("worldbody")
            if worldbody is None:
                worldbody = ET.SubElement(root, "worldbody")

            # Add back all spawned objects
            for handle, obj_info in self._handles.items():
                # Objects are already in the XML from previous spawn_asset calls
                # We just need to preserve the handles
                pass

            # Rebuild XML string
            self._model_xml = ET.tostring(root, encoding="unicode")

            # Reload model
            self._st.model = self._mujoco.MjModel.from_xml_string(self._model_xml)
            self._st.data = self._mujoco.MjData(self._st.model)

            # Recreate renderer with new model
            if self._st.renderer is not None:
                self._st.renderer = None
            self._st.renderer = self._mujoco.Renderer(self._st.model, height=self.h, width=self.w)

            # Rebuild handles mapping (body/geom IDs may have changed)
            # We'll need to find bodies by name
            self._rebuild_handles()

    def _rebuild_handles(self) -> None:
        """Rebuild handles mapping after model reload."""
        if self._st.model is None:
            return

        # Find bodies by name and update handles
        new_handles: Dict[str, _ObjectInfo] = {}
        for handle_name, old_info in self._handles.items():
            # Try to find body by name
            try:
                # Try different ways to access mjtObj enum
                obj_type = getattr(self._mujoco.mjtObj, "mjOBJ_BODY", None)
                if obj_type is None:
                    # Alternative: direct integer value (mjOBJ_BODY = 1)
                    obj_type = 1
                body_id = self._mujoco.mj_name2id(self._st.model, obj_type, handle_name)
                if body_id >= 0:
                    # Find the first geom for this body
                    geom_id = -1
                    for gid in range(self._st.model.ngeom):
                        if self._st.model.geom_bodyid[gid] == body_id:
                            geom_id = gid
                            break

                    if geom_id >= 0:
                        new_handles[handle_name] = _ObjectInfo(
                            body_id=body_id,
                            geom_id=geom_id,
                            instance_id=old_info.instance_id,  # Preserve instance ID
                        )
            except Exception:
                # If body not found, skip it
                pass

        self._handles = new_handles

    def spawn_asset(self, asset: AssetSpec, pose: Pose) -> str:
        """Spawn an asset into the scene.

        For MVP, creates a simple box or sphere geometry.
        Returns a handle (asset name) for later reference.
        """
        if self._st.model is None:
            raise RuntimeError("Backend not started. Call start() first.")

        # Parse current model XML
        root = ET.fromstring(self._model_xml)
        worldbody = root.find("worldbody")
        if worldbody is None:
            worldbody = ET.SubElement(root, "worldbody")

        # Create a body for this asset
        body = ET.SubElement(worldbody, "body")
        body.set("name", asset.name)

        # Set initial pose (position and quaternion)
        # MuJoCo uses (w, x, y, z) quaternion order
        qw, qx, qy, qz = pose.q[3], pose.q[0], pose.q[1], pose.q[2]
        body.set("pos", f"{pose.p[0]} {pose.p[1]} {pose.p[2]}")
        body.set("quat", f"{qw} {qx} {qy} {qz}")

        # Create a free joint so the body can move
        _freejoint = ET.SubElement(body, "freejoint")

        # Create geometry (use box for MVP, can be extended)
        # Use scale to determine size
        size = 0.1 * asset.scale  # Default 10cm, scaled
        geom = ET.SubElement(body, "geom")
        geom.set("type", "box")
        geom.set("size", f"{size} {size} {size}")
        geom.set("rgba", "0.8 0.2 0.2 1")  # Red color for visibility
        geom.set("name", f"{asset.name}_geom")

        # Rebuild model
        self._model_xml = ET.tostring(root, encoding="unicode")
        self._st.model = self._mujoco.MjModel.from_xml_string(self._model_xml)
        self._st.data = self._mujoco.MjData(self._st.model)

        # Recreate renderer
        if self._st.renderer is not None:
            self._st.renderer = None
        self._st.renderer = self._mujoco.Renderer(self._st.model, height=self.h, width=self.w)

        # Find the body and geom IDs
        # Try different ways to access mjtObj enum
        obj_type = getattr(self._mujoco.mjtObj, "mjOBJ_BODY", None)
        if obj_type is None:
            # Alternative: direct integer value (mjOBJ_BODY = 1)
            obj_type = 1
        body_id = self._mujoco.mj_name2id(self._st.model, obj_type, asset.name)
        geom_id = -1
        for gid in range(self._st.model.ngeom):
            if self._st.model.geom_bodyid[gid] == body_id:
                geom_id = gid
                break

        if body_id < 0 or geom_id < 0:
            raise RuntimeError(f"Failed to find spawned body/geom for {asset.name}")

        # Store handle with instance ID for segmentation
        instance_id = self._next_instance_id
        self._next_instance_id += 1

        self._handles[asset.name] = _ObjectInfo(
            body_id=body_id, geom_id=geom_id, instance_id=instance_id
        )

        return asset.name

    def set_pose(self, handle: str, pose: Pose) -> None:
        """Set the pose of an asset by handle.

        Converts from (x,y,z) position and (x,y,z,w) quaternion to MuJoCo format.
        """
        if handle not in self._handles:
            return

        if self._st.data is None or self._st.model is None:
            return

        obj_info = self._handles[handle]
        body_id = obj_info.body_id

        # Find qpos indices for this body's free joint
        # Free joints have 7 DOF: 3 for position, 4 for quaternion
        # Find the free joint for this body
        qpos_adr = self._st.model.jnt_qposadr
        jnt_type = self._st.model.jnt_type

        # Find the free joint for this body
        for jnt_id in range(self._st.model.njnt):
            if self._st.model.jnt_bodyid[jnt_id] == body_id:
                # Check if this is a free joint
                try:
                    is_free = jnt_type[jnt_id] == self._mujoco.mjtJoint.mjJNT_FREE
                except (AttributeError, TypeError):
                    # Fallback: try direct integer comparison (mjJNT_FREE = 0)
                    is_free = jnt_type[jnt_id] == 0

                if is_free:
                    qpos_idx = qpos_adr[jnt_id]
                    # Set position (x, y, z)
                    self._st.data.qpos[qpos_idx : qpos_idx + 3] = pose.p
                    # Set quaternion (w, x, y, z) - MuJoCo order
                    self._st.data.qpos[qpos_idx + 3 : qpos_idx + 7] = [
                        pose.q[3],
                        pose.q[0],
                        pose.q[1],
                        pose.q[2],
                    ]
                    # Forward kinematics to update body positions
                    self._mujoco.mj_forward(self._st.model, self._st.data)
                    return

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
        if self._st.model is None or self._st.data is None:
            return

        # MuJoCo uses fixed timestep from model, but we can step multiple times
        num_steps = max(1, int(dt / self._st.model.opt.timestep))
        for _ in range(num_steps):
            self._mujoco.mj_step(self._st.model, self._st.data)

    def _render_segmentation_colorid(self) -> np.ndarray:
        """Render segmentation using color-id method.

        Renders each object with a unique flat color, then maps colors to instance IDs.
        Returns int32 HxW array where 0=background, 1..K are instance IDs.
        """
        if self._st.renderer is None or self._st.model is None or self._st.data is None:
            return np.zeros((self.h, self.w), dtype=np.int32)

        if not self._handles:
            # No objects to segment
            return np.zeros((self.h, self.w), dtype=np.int32)

        # Store original colors
        original_rgba = self._st.model.geom_rgba.copy()

        # Create color mapping: instance_id -> RGB color
        # Use deterministic colors based on instance_id
        color_map: Dict[int, tuple] = {}
        for handle, obj_info in self._handles.items():
            instance_id = obj_info.instance_id
            # Generate a deterministic color from instance_id
            # Use a hash-like function to get distinct colors
            r = (instance_id * 17) % 256
            g = (instance_id * 31) % 256
            b = (instance_id * 47) % 256
            color_map[instance_id] = (r, g, b)

        # Render with color-id: set each geom to its unique color
        for handle, obj_info in self._handles.items():
            geom_id = obj_info.geom_id
            instance_id = obj_info.instance_id
            if instance_id in color_map:
                r, g, b = color_map[instance_id]
                # Set geom color (RGBA, normalized 0-1)
                self._st.model.geom_rgba[geom_id] = [r / 255.0, g / 255.0, b / 255.0, 1.0]

        # Get camera setup (same as main render)
        camera_pos = None
        if self._sensors:
            sensor_name = list(self._sensors.keys())[0]
            sensor_cfg = self._sensors[sensor_name]
            pose = sensor_cfg["pose"]
            camera_pos = np.array(pose.p)

        # Create scene and camera for rendering
        scene = self._mujoco.MjvScene(self._st.model, maxgeom=10000)
        camera = self._mujoco.MjvCamera()

        if camera_pos is not None:
            camera.lookat[:] = [0, 0, 0]
            dist = np.linalg.norm(camera_pos)
            camera.distance = dist
            x, y, z = camera_pos
            azimuth = np.arctan2(y, x) * 180 / np.pi
            elevation = np.arcsin(z / dist) * 180 / np.pi if dist > 0 else 0
            camera.azimuth = azimuth
            camera.elevation = elevation

        # Update scene
        # Get category bit - try different ways to access
        try:
            cat_bit = self._mujoco.mjtCatBit.mjCAT_ALL
        except (AttributeError, TypeError):
            # Fallback: try direct access or use all bits
            try:
                cat_bit = getattr(self._mujoco.mjtCatBit, "mjCAT_ALL", 0xFFFFFFFF)
            except Exception:
                cat_bit = 0xFFFFFFFF  # All categories

        self._mujoco.mjv_updateScene(
            self._st.model,
            self._st.data,
            self._mujoco.MjvOption(),
            None,  # pert
            camera,
            cat_bit,
            scene,
        )

        # Render
        # Try with scene and camera first, fallback to just data
        try:
            self._st.renderer.update_scene(self._st.data, scene=scene, camera=camera)
        except TypeError:
            # Fallback: update_scene may only take data
            self._st.renderer.update_scene(self._st.data)
        seg_rgb = self._st.renderer.render()

        # Convert to uint8 if needed
        if seg_rgb.dtype == np.float32 or seg_rgb.dtype == np.float64:
            seg_rgb = (np.clip(seg_rgb, 0, 1) * 255).astype(np.uint8)
        else:
            seg_rgb = seg_rgb.astype(np.uint8)

        # Restore original colors
        self._st.model.geom_rgba[:] = original_rgba

        # Map colors back to instance IDs
        seg_mask = np.zeros((self.h, self.w), dtype=np.int32)

        for instance_id, (r, g, b) in color_map.items():
            # Find pixels matching this color (with some tolerance for rendering artifacts)
            mask = (
                (np.abs(seg_rgb[:, :, 0].astype(int) - r) < 3)
                & (np.abs(seg_rgb[:, :, 1].astype(int) - g) < 3)
                & (np.abs(seg_rgb[:, :, 2].astype(int) - b) < 3)
            )
            seg_mask[mask] = instance_id

        return seg_mask

    def render(self) -> FrameBundle:
        """Render the current scene and return FrameBundle.

        Renders RGB, depth, and segmentation.
        """
        if self._st.model is None or self._st.data is None:
            rgb = np.zeros((self.h, self.w, 3), dtype=np.uint8)
            return FrameBundle(
                rgb=rgb, depth=None, seg=None, meta={"backend": "mujoco", "note": "not initialized"}
            )

        if self._st.renderer is None:
            rgb = np.zeros((self.h, self.w, 3), dtype=np.uint8)
            return FrameBundle(
                rgb=rgb,
                depth=None,
                seg=None,
                meta={"backend": "mujoco", "note": "renderer not initialized"},
            )

        # Get camera from first sensor (or use default)
        camera_pos = None
        if self._sensors:
            sensor_name = list(self._sensors.keys())[0]
            sensor_cfg = self._sensors[sensor_name]
            pose = sensor_cfg["pose"]
            camera_pos = np.array(pose.p)

        # Create scene and camera for rendering
        scene = self._mujoco.MjvScene(self._st.model, maxgeom=10000)
        camera = self._mujoco.MjvCamera()
        option = self._mujoco.MjvOption()

        # Set up camera based on sensor pose
        if camera_pos is not None:
            # Compute lookat point (look at origin for now)
            camera.lookat[:] = [0, 0, 0]
            # Compute distance and angles from position
            dist = np.linalg.norm(camera_pos)
            camera.distance = dist
            # Compute azimuth and elevation from position
            # Position is in world coordinates
            x, y, z = camera_pos
            azimuth = np.arctan2(y, x) * 180 / np.pi
            elevation = np.arcsin(z / dist) * 180 / np.pi if dist > 0 else 0
            camera.azimuth = azimuth
            camera.elevation = elevation

        # Update scene
        # Get category bit - try different ways to access
        try:
            cat_bit = self._mujoco.mjtCatBit.mjCAT_ALL
        except (AttributeError, TypeError):
            # Fallback: try direct access or use all bits
            try:
                cat_bit = getattr(self._mujoco.mjtCatBit, "mjCAT_ALL", 0xFFFFFFFF)
            except Exception:
                cat_bit = 0xFFFFFFFF  # All categories

        self._mujoco.mjv_updateScene(
            self._st.model,
            self._st.data,
            option,
            None,  # pert
            camera,
            cat_bit,
            scene,
        )

        # Render RGB - disable depth rendering first to get RGB
        try:
            self._st.renderer.disable_depth_rendering()
        except (AttributeError, Exception):
            pass  # May not be enabled, that's fine

        # Update scene and render RGB
        try:
            self._st.renderer.update_scene(self._st.data, scene=scene, camera=camera)
        except TypeError:
            # Fallback: update_scene may only take data
            self._st.renderer.update_scene(self._st.data)

        rgb = self._st.renderer.render()
        # Convert from float [0,1] to uint8 [0,255] if needed
        if rgb.dtype == np.float32 or rgb.dtype == np.float64:
            rgb = (np.clip(rgb, 0, 1) * 255).astype(np.uint8)
        else:
            rgb = rgb.astype(np.uint8)

        # Render depth - enable depth rendering and render again
        depth = None
        try:
            # Enable depth rendering
            self._st.renderer.enable_depth_rendering()
            # Update scene again (needed after enabling depth)
            try:
                self._st.renderer.update_scene(self._st.data, scene=scene, camera=camera)
            except TypeError:
                self._st.renderer.update_scene(self._st.data)
            # Render depth (returns 2D float32 array when depth is enabled)
            depth_buffer = self._st.renderer.render()
            if depth_buffer is not None and len(depth_buffer.shape) == 2:
                # Depth is in meters (or normalized, depending on MuJoCo version)
                # MuJoCo typically returns depth in meters
                depth = depth_buffer.astype(np.float32)
            # Disable depth rendering for next RGB render
            self._st.renderer.disable_depth_rendering()
        except Exception:
            # If depth rendering fails, continue without depth
            depth = None
            try:
                self._st.renderer.disable_depth_rendering()
            except Exception:
                pass

        # Render segmentation using color-id method
        seg = self._render_segmentation_colorid()

        # Build metadata
        meta = {
            "backend": "mujoco",
            "backend_version": self._st.mujoco_version,
            "width": self.w,
            "height": self.h,
            "seg_encoding": "instance_id int32 (0=background, 1..K=instances)",
            "depth_encoding": "normalized float32 [0,1]" if depth is not None else None,
        }

        return FrameBundle(rgb=rgb, depth=depth, seg=seg, meta=meta)


register_backend("mujoco", MuJoCoBackend)
