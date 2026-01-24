"""Smoke tests for Isaac Sim backend.

Verifies backend integration, protocol compliance, and basic functionality.
Most tests work on Mac (without Isaac Sim installed).
See tests/README_isaac_sim_backend_tests.md for detailed documentation.
"""

import pytest
from komansim.core.backend import SimBackend
from komansim.core.registry import make_backend
from komansim.core.types import AssetSpec, FrameBundle, Pose, SceneSpec, SensorSpec


def _isaac_sim_available() -> bool:
    """Check if Isaac Sim is available (will be False on Mac)."""
    try:
        from isaacsim.simulation_app import SimulationApp  # type: ignore  # noqa: F401

        return True
    except (ImportError, ModuleNotFoundError):
        return False


def test_isaac_sim_backend_registered():
    """Test that Isaac Sim backend is registered after import."""
    import komansim.backends.isaac_sim.backend  # noqa: F401

    backend = make_backend("isaac_sim", headless=True, width=640, height=480)
    assert backend is not None
    assert isinstance(backend, SimBackend)


def test_isaac_sim_backend_implements_protocol():
    """Test that Isaac Sim backend implements SimBackend protocol."""
    import komansim.backends.isaac_sim.backend  # noqa: F401
    from komansim.backends.isaac_sim.backend import IsaacSimBackend

    assert isinstance(IsaacSimBackend, type)
    backend = IsaacSimBackend(headless=True, width=640, height=480)
    assert isinstance(backend, SimBackend)


def test_isaac_sim_backend_instantiation():
    """Test basic backend instantiation with various parameters."""
    import komansim.backends.isaac_sim.backend  # noqa: F401

    # Test with defaults
    backend = make_backend("isaac_sim", headless=True)
    assert backend.headless is True
    assert backend.w == 1280  # default width
    assert backend.h == 720  # default height

    # Test with custom dimensions
    backend = make_backend("isaac_sim", headless=False, width=800, height=600)
    assert backend.headless is False
    assert backend.w == 800
    assert backend.h == 600

    # Test with extra kwargs
    backend = make_backend("isaac_sim", headless=True, width=640, height=480, experience="test")
    assert backend.experience == "test"


def test_isaac_sim_backend_lifecycle_without_isaac():
    """Test backend lifecycle when Isaac Sim is not installed (expected on Mac)."""
    import komansim.backends.isaac_sim.backend  # noqa: F401

    backend = make_backend("isaac_sim", headless=True, width=64, height=64)

    # Should raise RuntimeError when Isaac Sim is not installed
    try:
        backend.start()
        # If we get here, Isaac Sim is installed, so test close
        backend.close()
    except RuntimeError as e:
        # Expected when Isaac Sim is not installed - verify helpful error message
        assert "isaac" in str(e).lower() or "python env" in str(e).lower()


@pytest.mark.skipif(
    not _isaac_sim_available(),
    reason="Isaac Sim not available (expected on Mac) - requires Linux/Windows with Isaac Sim installed",
)
def test_isaac_sim_backend_lifecycle():
    """Test full backend lifecycle when Isaac Sim is installed."""
    import komansim.backends.isaac_sim.backend  # noqa: F401

    backend = make_backend("isaac_sim", headless=True, width=64, height=64)

    backend.start()
    backend.close()

    # Can start again after close
    backend.start()
    backend.close()


@pytest.mark.skipif(not _isaac_sim_available(), reason="Isaac Sim not available")
def test_isaac_sim_backend_basic_operations():
    """Test basic operations when Isaac Sim is installed."""
    import komansim.backends.isaac_sim.backend  # noqa: F401

    backend = make_backend("isaac_sim", headless=True, width=64, height=64)
    backend.start()

    try:
        # Test reset
        backend.reset(seed=42)

        # Test scene loading
        scene = SceneSpec(usd_path=None, physics_dt=0.01, dome_light_intensity=1000.0)
        backend.load_scene(scene)

        # Test asset spawning
        asset = AssetSpec(
            name="test_asset", usd_path="dummy.usd", semantic_label="object", scale=1.0
        )
        pose = Pose(p=(0.0, 0.0, 1.0), q=(0.0, 0.0, 0.0, 1.0))
        handle = backend.spawn_asset(asset, pose)
        assert handle == "test_asset"

        # Test pose setting
        new_pose = Pose(p=(1.0, 0.0, 1.0), q=(0.0, 0.0, 0.0, 1.0))
        backend.set_pose(handle, new_pose)

        # Test sensor addition
        sensor = SensorSpec(
            name="cam0",
            type="camera_rgb",
            pose=Pose(p=(2.0, 2.0, 2.0), q=(0.0, 0.0, 0.0, 1.0)),
            intrinsics={"fx": 500, "fy": 500, "cx": 32, "cy": 32},
        )
        sensor_handle = backend.add_sensor(sensor)
        assert sensor_handle == "cam0"

        # Test step
        backend.step(0.01)

        # Test render (should return FrameBundle even if placeholder)
        frame = backend.render()
        assert isinstance(frame, FrameBundle)
        assert frame.rgb is not None
        assert frame.rgb.shape == (64, 64, 3)
        assert frame.meta is not None
        assert frame.meta.get("backend") == "isaac_sim"

    finally:
        backend.close()


def test_isaac_sim_backend_method_signatures():
    """Test that all required methods exist and are callable."""
    import komansim.backends.isaac_sim.backend  # noqa: F401
    from komansim.backends.isaac_sim.backend import IsaacSimBackend

    backend = IsaacSimBackend(headless=True, width=64, height=64)

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


def test_isaac_sim_backend_render_returns_framebundle():
    """Test that render() returns FrameBundle even when not initialized."""
    import komansim.backends.isaac_sim.backend  # noqa: F401

    backend = make_backend("isaac_sim", headless=True, width=64, height=64)

    # Should return FrameBundle even without start()
    frame = backend.render()
    assert isinstance(frame, FrameBundle)
    assert frame.rgb is not None
    assert frame.rgb.shape == (64, 64, 3)
    assert frame.meta is not None


def test_isaac_sim_backend_multiple_sensors():
    """Test adding multiple sensors."""
    import komansim.backends.isaac_sim.backend  # noqa: F401

    backend = make_backend("isaac_sim", headless=True, width=64, height=64)

    sensor1 = SensorSpec(
        name="cam1",
        type="camera_rgb",
        pose=Pose(p=(1.0, 1.0, 1.0), q=(0.0, 0.0, 0.0, 1.0)),
        intrinsics={"fx": 500, "fy": 500, "cx": 32, "cy": 32},
    )

    sensor2 = SensorSpec(
        name="cam2",
        type="camera_depth",
        pose=Pose(p=(2.0, 2.0, 2.0), q=(0.0, 0.0, 0.0, 1.0)),
        intrinsics={"fx": 500, "fy": 500, "cx": 32, "cy": 32},
    )

    handle1 = backend.add_sensor(sensor1)
    handle2 = backend.add_sensor(sensor2)

    assert handle1 == "cam1"
    assert handle2 == "cam2"
    assert len(backend._sensors) == 2
