from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional
import numpy as np

from komansim.core.registry import register_backend
from komansim.core.types import AssetSpec, FrameBundle, Pose, SceneSpec, SensorSpec


@dataclass
class _IsaacState:
    simulation_app: Any = None
    stage: Any = None
    context: Any = None
    cameras: Dict[str, Any] = field(default_factory=dict)
    replicator: Any = None


class IsaacSimBackend:
    """Isaac Sim backend scaffold.

    IMPORTANT:
    - This backend must run inside Isaac Sim's python environment.
    - Kit extensions require the order: start SimulationApp -> then import omni/replicator.
    - In this initial version, `render()` returns a placeholder image until you wire Replicator annotators.
    """

    def __init__(self, headless=True, width=1280, height=720, experience: str = "", **kwargs):
        self.headless = bool(headless)
        self.w = int(width)
        self.h = int(height)
        self.experience = experience or ""
        self.extra = kwargs
        self._st = _IsaacState()
        self._handles: Dict[str, str] = {}
        self._sensors: Dict[str, Dict[str, Any]] = {}
        self._omni = None
        self._rep = None

    def start(self) -> None:
        try:
            from isaacsim.simulation_app import SimulationApp  # type: ignore
        except Exception as e:
            raise RuntimeError(
                "IsaacSimBackend must run inside Isaac Sim's python env. "
                "Use Isaac's python.sh/python.bat to launch."
            ) from e

        cfg = {"headless": self.headless, "width": self.w, "height": self.h}
        self._st.simulation_app = SimulationApp(cfg, experience=self.experience)

        # After SimulationApp starts, you may safely import omni/replicator.
        try:
            import omni
            import omni.usd
            import omni.replicator.core as rep
            from pxr import Usd, UsdGeom, Gf

            self._omni = omni
            self._rep = rep
            self._Usd = Usd
            self._UsdGeom = UsdGeom
            self._Gf = Gf

            # Initialize replicator
            rep.orchestrator._orchestrator._is_started = True
        except ImportError:
            # If imports fail, backend will still work but with limited functionality
            pass

    def close(self) -> None:
        if self._st.simulation_app is not None:
            self._st.simulation_app.close()
            self._st.simulation_app = None
        self._st.stage = None
        self._st.context = None
        self._st.cameras = {}

    def reset(self, seed: Optional[int] = None) -> None:
        """Reset simulation state and optionally set random seed."""
        if self._omni is None:
            return

        # Set random seed if provided
        if seed is not None:
            import random

            random.seed(seed)
            np.random.seed(seed)

        # Create new stage or clear existing one
        if self._st.stage is not None:
            # Clear existing stage
            stage = self._st.stage
            root_prim = stage.GetPrimAtPath("/World")
            if root_prim.IsValid():
                # Remove all children except default prims
                for child in root_prim.GetChildren():
                    if child.GetName() not in ["defaultLight", "defaultGroundPlane"]:
                        stage.RemovePrim(child.GetPath())

        # Reset handles and sensors
        self._handles.clear()
        self._sensors.clear()
        self._st.cameras = {}

    def load_scene(self, scene: SceneSpec) -> None:
        """Load or create scene from SceneSpec."""
        if self._omni is None:
            return

        try:
            from pxr import Usd, UsdGeom

            # Get or create stage
            if scene.usd_path:
                # Load existing USD stage
                stage_path = scene.usd_path
                self._st.stage = Usd.Stage.Open(stage_path)
                if not self._st.stage:
                    raise RuntimeError(f"Failed to open USD stage: {stage_path}")
            else:
                # Create new default stage
                self._st.stage = Usd.Stage.CreateNew("memory:scene.usd")

                # Set up default scene
                root_prim = self._st.stage.DefinePrim("/World", "Xform")
                self._st.stage.SetDefaultPrim(root_prim)

                # Add default ground plane
                ground = UsdGeom.Plane.Define(self._st.stage, "/World/defaultGroundPlane")
                ground.CreateSizeAttr(100.0)

                # Add dome light
                light = UsdGeom.DomeLight.Define(self._st.stage, "/World/defaultLight")
                light.CreateIntensityAttr(scene.dome_light_intensity)

            # Set physics timestep
            # Note: Physics settings are typically set via PhysicsScene prim
            # For now, we'll rely on default physics settings

        except Exception:
            # If USD operations fail, continue with placeholder
            # This allows the scaffold to work even without full USD setup
            pass

    def spawn_asset(self, asset: AssetSpec, pose: Pose) -> str:
        """Spawn an asset into the scene."""
        if self._omni is None or self._st.stage is None:
            # Store handle for later even if stage not available
            self._handles[asset.name] = f"/World/Assets/{asset.name}"
            return asset.name

        try:
            from pxr import UsdGeom, Gf

            # Ensure /World/Assets exists
            assets_path = "/World/Assets"
            assets_prim = self._st.stage.GetPrimAtPath(assets_path)
            if not assets_prim.IsValid():
                assets_prim = self._st.stage.DefinePrim(assets_path, "Xform")

            # Create prim for this asset
            asset_path = f"{assets_path}/{asset.name}"

            if asset.usd_path and asset.usd_path != "PATH/TO/YOUR_ASSET.usd":
                # Reference external USD file
                asset_prim = self._st.stage.DefinePrim(asset_path)
                asset_prim.GetReferences().AddReference(asset.usd_path)
            else:
                # Create placeholder geometry (cube) if USD path not provided
                asset_prim = UsdGeom.Cube.Define(self._st.stage, asset_path)
                asset_prim.CreateSizeAttr(0.1)  # 10cm cube placeholder

            # Set initial pose
            xform = UsdGeom.Xformable(asset_prim)
            translate = Gf.Vec3d(pose.p[0], pose.p[1], pose.p[2])
            _rotate = Gf.Quatf(
                pose.q[3], pose.q[0], pose.q[1], pose.q[2]
            )  # w, x, y, z (TODO: use for rotation)

            xform_op = xform.AddTranslateOp()
            xform_op.Set(translate)

            rot_op = xform.AddRotateXYZOp()
            # Convert quaternion to Euler (simplified - just set rotation)
            rot_op.Set(Gf.Vec3f(0, 0, 0))  # Placeholder - full quat to euler conversion needed

            # Set scale
            if asset.scale != 1.0:
                scale_op = xform.AddScaleOp()
                scale_op.Set(Gf.Vec3f(asset.scale, asset.scale, asset.scale))

            # Store handle
            self._handles[asset.name] = asset_path

        except Exception:
            # Fallback: just store handle
            self._handles[asset.name] = f"/World/Assets/{asset.name}"

        return asset.name

    def set_pose(self, handle: str, pose: Pose) -> None:
        """Set the pose of an asset by handle."""
        if self._omni is None or self._st.stage is None:
            return

        if handle not in self._handles:
            return

        try:
            from pxr import UsdGeom, Gf

            prim_path = self._handles[handle]
            prim = self._st.stage.GetPrimAtPath(prim_path)

            if not prim.IsValid():
                return

            xform = UsdGeom.Xformable(prim)
            if not xform:
                return

            # Set translation
            translate = Gf.Vec3d(pose.p[0], pose.p[1], pose.p[2])

            # Get or create translate op
            xform_ops = xform.GetOrderedXformOps()
            translate_op = None
            for op in xform_ops:
                if op.GetOpType() == UsdGeom.XformOp.TypeTranslate:
                    translate_op = op
                    break

            if translate_op:
                translate_op.Set(translate)
            else:
                translate_op = xform.AddTranslateOp()
                translate_op.Set(translate)

            # Set rotation (quaternion to rotation)
            # Note: Full quaternion support requires proper conversion
            # For now, we'll set a basic rotation
            # TODO: Implement full quaternion to Euler conversion

        except Exception:
            # Silently fail if pose setting doesn't work
            pass

    def add_sensor(self, sensor: SensorSpec) -> str:
        """Add a camera sensor to the scene."""
        if self._omni is None or self._st.stage is None:
            # Store sensor config for later
            self._sensors[sensor.name] = {
                "pose": sensor.pose,
                "intrinsics": sensor.intrinsics,
                "type": sensor.type,
            }
            return sensor.name

        try:
            from pxr import UsdGeom, Gf

            # Ensure /World/Cameras exists
            cameras_path = "/World/Cameras"
            cameras_prim = self._st.stage.GetPrimAtPath(cameras_path)
            if not cameras_prim.IsValid():
                cameras_prim = self._st.stage.DefinePrim(cameras_path, "Xform")

            # Create camera prim
            camera_path = f"{cameras_path}/{sensor.name}"
            camera_prim = UsdGeom.Camera.Define(self._st.stage, camera_path)

            # Set camera pose
            xform = UsdGeom.Xformable(camera_prim)
            translate = Gf.Vec3d(sensor.pose.p[0], sensor.pose.p[1], sensor.pose.p[2])
            translate_op = xform.AddTranslateOp()
            translate_op.Set(translate)

            # Set camera intrinsics
            camera = camera_prim.GetCamera()
            focal_length = sensor.intrinsics.get("fx", 800.0)
            # Convert focal length to horizontal aperture
            # Approximate: horizontalAperture = (focal_length * sensor_width) / image_width
            sensor_width = 36.0  # mm (typical full-frame sensor)
            image_width = self.w
            horizontal_aperture = (focal_length * sensor_width) / image_width
            camera.CreateHorizontalApertureAttr(horizontal_aperture)

            # Set resolution
            camera.CreateHorizontalApertureOffsetAttr(0.0)
            camera.CreateVerticalApertureOffsetAttr(0.0)

            # Store camera and sensor config
            self._st.cameras[sensor.name] = camera_prim
            self._sensors[sensor.name] = {
                "pose": sensor.pose,
                "intrinsics": sensor.intrinsics,
                "type": sensor.type,
                "prim": camera_prim,
            }

        except Exception:
            # Fallback: just store sensor config
            self._sensors[sensor.name] = {
                "pose": sensor.pose,
                "intrinsics": sensor.intrinsics,
                "type": sensor.type,
            }

        return sensor.name

    def step(self, dt: float) -> None:
        # Common pattern: app.update() drives simulation/rendering.
        if self._st.simulation_app is not None:
            self._st.simulation_app.update()

    def render(self) -> FrameBundle:
        """Render the current scene and return FrameBundle."""
        if self._omni is None or self._st.stage is None:
            # Return placeholder if not initialized
            rgb = np.zeros((self.h, self.w, 3), dtype=np.uint8)
            return FrameBundle(
                rgb=rgb,
                depth=None,
                seg=None,
                meta={"backend": "isaac_sim", "note": "not initialized"},
            )

        try:
            # Use first camera if available
            if not self._sensors:
                rgb = np.zeros((self.h, self.w, 3), dtype=np.uint8)
                return FrameBundle(
                    rgb=rgb,
                    depth=None,
                    seg=None,
                    meta={"backend": "isaac_sim", "note": "no cameras"},
                )

            sensor_name = list(self._sensors.keys())[0]
            sensor_cfg = self._sensors[sensor_name]

            # Set up Replicator render product
            # Note: This is a simplified implementation
            # Full implementation would use rep.create.render_product() and annotators

            # For now, return placeholder with metadata
            # TODO: Implement full Replicator pipeline:
            # 1. Create render product from camera
            # 2. Add RGB annotator
            # 3. Add depth annotator (if depth camera)
            # 4. Add segmentation annotator
            # 5. Trigger render and get data

            rgb = np.zeros((self.h, self.w, 3), dtype=np.uint8)
            depth = None
            seg = None

            # Check if this is a depth camera
            if sensor_cfg.get("type") == "camera_depth":
                depth = np.zeros((self.h, self.w), dtype=np.float32)

            meta = {
                "backend": "isaac_sim",
                "width": self.w,
                "height": self.h,
                "camera": sensor_name,
                "note": "scaffold - Replicator integration needed for actual rendering",
            }

            return FrameBundle(rgb=rgb, depth=depth, seg=seg, meta=meta)

        except Exception as e:
            # Fallback to placeholder
            rgb = np.zeros((self.h, self.w, 3), dtype=np.uint8)
            return FrameBundle(
                rgb=rgb,
                depth=None,
                seg=None,
                meta={"backend": "isaac_sim", "note": f"render error: {str(e)}"},
            )


register_backend("isaac_sim", IsaacSimBackend)
