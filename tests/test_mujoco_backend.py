"""Smoke tests for MuJoCo backend.

Verifies backend integration, protocol compliance, and basic functionality.
See tests/README_mujoco_backend_tests.md for detailed documentation.
"""

import pytest
from komansim.core.backend import SimBackend
from komansim.core.registry import make_backend
from komansim.core.types import AssetSpec, FrameBundle, Pose, SceneSpec, SensorSpec


def _mujoco_available() -> bool:
    """Check if MuJoCo package is available for import."""
    try:
        import mujoco  # noqa: F401

        return True
    except ImportError:
        return False


def test_mujoco_backend_registered():
    """Test that MuJoCo backend is registered after import."""
    # Import triggers registration (side-effect of module import)
    import komansim.backends.mujoco.backend  # noqa: F401

    # Should be able to create backend via registry
    backend = make_backend("mujoco", headless=True, width=640, height=480)
    assert backend is not None
    assert isinstance(backend, SimBackend)


def test_mujoco_backend_implements_protocol():
    """Test that MuJoCo backend implements SimBackend protocol."""
    import komansim.backends.mujoco.backend  # noqa: F401
    from komansim.backends.mujoco.backend import MuJoCoBackend

    # Runtime checkable protocol - verify class and instance
    assert isinstance(MuJoCoBackend, type)
    backend = MuJoCoBackend(headless=True, width=640, height=480)
    assert isinstance(backend, SimBackend)


def test_mujoco_backend_instantiation():
    """Test basic backend instantiation with various parameters."""
    import komansim.backends.mujoco.backend  # noqa: F401

    # Test with defaults
    backend = make_backend("mujoco", headless=True)
    assert backend.headless is True
    assert backend.w == 1280  # default width
    assert backend.h == 720  # default height

    # Test with custom dimensions
    backend = make_backend("mujoco", headless=False, width=800, height=600)
    assert backend.headless is False
    assert backend.w == 800
    assert backend.h == 600

    # Test with extra kwargs (for future extensibility)
    backend = make_backend("mujoco", headless=True, width=640, height=480, extra_param="test")
    assert backend.extra.get("extra_param") == "test"


def test_mujoco_backend_lifecycle_without_mujoco():
    """Test backend lifecycle when MuJoCo is not installed (should raise error on start)."""
    import komansim.backends.mujoco.backend  # noqa: F401

    backend = make_backend("mujoco", headless=True, width=64, height=64)

    # Should raise RuntimeError when mujoco is not installed
    try:
        backend.start()
        # If we get here, mujoco is installed, so test close
        backend.close()
    except RuntimeError as e:
        # Expected when mujoco is not installed - verify helpful error message
        assert "mujoco" in str(e).lower() or "requires" in str(e).lower()


@pytest.mark.skipif(
    not _mujoco_available(),
    reason="MuJoCo not installed - install with 'pip install mujoco' to run full tests",
)
def test_mujoco_backend_lifecycle():
    """Test full backend lifecycle when MuJoCo is installed."""
    import komansim.backends.mujoco.backend  # noqa: F401

    backend = make_backend("mujoco", headless=True, width=64, height=64)

    # Start should succeed
    backend.start()

    # Close should succeed
    backend.close()

    # Can start again after close (idempotent)
    backend.start()
    backend.close()


@pytest.mark.skipif(not _mujoco_available(), reason="MuJoCo not installed")
def test_mujoco_backend_basic_operations():
    """Test basic operations when MuJoCo is installed."""
    import komansim.backends.mujoco.backend  # noqa: F401

    backend = make_backend("mujoco", headless=True, width=64, height=64)
    backend.start()

    try:
        # Test reset with seed (for reproducibility)
        backend.reset(seed=42)

        # Test scene loading (creates default scene if usd_path is None)
        scene = SceneSpec(usd_path=None, physics_dt=0.01, dome_light_intensity=1000.0)
        backend.load_scene(scene)

        # Test asset spawning (returns handle for later reference)
        asset = AssetSpec(
            name="test_asset", usd_path="dummy.mjcf", semantic_label="object", scale=1.0
        )
        pose = Pose(p=(0.0, 0.0, 1.0), q=(0.0, 0.0, 0.0, 1.0))
        handle = backend.spawn_asset(asset, pose)
        assert handle == "test_asset"

        # Test pose setting (update asset position/orientation)
        new_pose = Pose(p=(1.0, 0.0, 1.0), q=(0.0, 0.0, 0.0, 1.0))
        backend.set_pose(handle, new_pose)

        # Test sensor addition (camera with intrinsics)
        sensor = SensorSpec(
            name="cam0",
            type="camera_rgb",
            pose=Pose(p=(2.0, 2.0, 2.0), q=(0.0, 0.0, 0.0, 1.0)),
            intrinsics={"fx": 500, "fy": 500, "cx": 32, "cy": 32},
        )
        sensor_handle = backend.add_sensor(sensor)
        assert sensor_handle == "cam0"

        # Test step (advance physics simulation)
        backend.step(0.01)

        # Test render (should return FrameBundle with correct shape)
        frame = backend.render()
        assert isinstance(frame, FrameBundle)
        assert frame.rgb is not None
        assert frame.rgb.shape == (64, 64, 3)  # (height, width, channels)
        assert frame.meta is not None
        assert frame.meta.get("backend") == "mujoco"

    finally:
        backend.close()


def test_mujoco_backend_method_signatures():
    """Test that all required methods exist and are callable."""
    import komansim.backends.mujoco.backend  # noqa: F401
    from komansim.backends.mujoco.backend import MuJoCoBackend

    backend = MuJoCoBackend(headless=True, width=64, height=64)

    # Check all protocol methods exist
    required_methods = [
        "start",
        "close",
        "reset",
        "load_scene",
        "spawn_asset",
        "set_pose",
        "add_sensor",
        "step",
        "render",
    ]
    for method_name in required_methods:
        assert hasattr(backend, method_name), f"Missing method: {method_name}"
        assert callable(getattr(backend, method_name)), f"Method not callable: {method_name}"


def test_mujoco_backend_render_returns_framebundle():
    """Test that render() returns FrameBundle even when not initialized."""
    import komansim.backends.mujoco.backend  # noqa: F401

    backend = make_backend("mujoco", headless=True, width=64, height=64)

    # Should return FrameBundle even without start()
    # (though it will be a placeholder with zeros)
    frame = backend.render()
    assert isinstance(frame, FrameBundle)
    assert frame.rgb is not None
    assert frame.rgb.shape == (64, 64, 3)  # Matches backend dimensions
    assert frame.meta is not None


def test_mujoco_backend_multiple_sensors():
    """Test adding multiple sensors."""
    import komansim.backends.mujoco.backend  # noqa: F401

    backend = make_backend("mujoco", headless=True, width=64, height=64)

    # Add first sensor (RGB camera)
    sensor1 = SensorSpec(
        name="cam1",
        type="camera_rgb",
        pose=Pose(p=(1.0, 1.0, 1.0), q=(0.0, 0.0, 0.0, 1.0)),
        intrinsics={"fx": 500, "fy": 500, "cx": 32, "cy": 32},
    )

    # Add second sensor (depth camera)
    sensor2 = SensorSpec(
        name="cam2",
        type="camera_depth",
        pose=Pose(p=(2.0, 2.0, 2.0), q=(0.0, 0.0, 0.0, 1.0)),
        intrinsics={"fx": 500, "fy": 500, "cx": 32, "cy": 32},
    )

    handle1 = backend.add_sensor(sensor1)
    handle2 = backend.add_sensor(sensor2)

    # Verify handles match sensor names
    assert handle1 == "cam1"
    assert handle2 == "cam2"
    # Verify both sensors are stored
    assert len(backend._sensors) == 2
