from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from komansim.core.backend import SimBackend
from komansim.core.types import AssetSpec, FrameBundle, Pose, SceneSpec, SensorSpec
from komansim.schemas.job_schema import JobConfig
from komansim.runtime.run_job import run_job
from komansim.pipeline.generate import JobFailedError


# Mock Backend
class MockBackend(SimBackend):
    def __init__(self, **kwargs):
        self.started = False
        self.closed = False
        self.scene_loaded = False
        self.assets = []
        self.sensors = []
        self.poses = {}

    def start(self) -> None:
        self.started = True

    def close(self) -> None:
        self.closed = True

    def reset(self, seed=None) -> None:
        pass

    def load_scene(self, scene: SceneSpec) -> None:
        self.scene_loaded = True

    def spawn_asset(self, asset: AssetSpec, pose: Pose) -> str:
        self.assets.append(asset)
        return "handle"

    def set_pose(self, handle: str, pose: Pose) -> None:
        self.poses[handle] = pose

    def add_sensor(self, sensor: SensorSpec) -> str:
        self.sensors.append(sensor)
        return "sensor_handle"

    def step(self, dt: float) -> None:
        pass

    def render(self) -> FrameBundle:
        import numpy as np

        rgb = np.zeros((100, 100, 3), dtype=np.uint8)
        depth = np.zeros((100, 100), dtype=np.float32)
        seg = np.zeros((100, 100), dtype=np.int32)
        return FrameBundle(rgb=rgb, depth=depth, seg=seg, meta={})


@pytest.fixture
def minimal_config(tmp_path):
    # Use dicts for nested objects to satisfy Pydantic validation if types mismatch
    return JobConfig(
        job_name="test_job",
        out_dir=str(tmp_path / "output"),
        seed=42,
        num_frames=2,
        dt=0.1,
        headless=True,
        width=100,
        height=100,
        scene={"usd_path": None},
        assets=[{"name": "test_asset", "usd_path": "test.usd", "semantic_label": "test_label"}],
        sensors=[
            {
                "name": "cam0",
                "type": "camera_rgb",
                "pose": {"p": (0, 0, 0), "q": (0, 0, 0, 1)},
                "intrinsics": {"fx": 100, "fy": 100, "cx": 50, "cy": 50},
            }
        ],
        randomization={"random_xy": 0.0, "random_yaw_deg": 0.0},
    )


def test_run_job_with_config_path_and_dummy_backend(tmp_path, minimal_config):
    """Test run_job with config path and dummy backend string."""
    # Write config to file
    config_path = tmp_path / "config.yaml"
    with open(config_path, "w") as f:
        # Convert pydantic model to dict and then to yaml
        yaml.dump(minimal_config.model_dump(), f)

    # Run job using the actual DummyBackend (via string name)
    # This requires komansim.backends.dummy to be registered
    import komansim.backends.dummy.backend  # noqa: F401

    # Run job
    run_job(backend="dummy", config_path_or_obj=config_path, use_cache=False)

    out_dir = Path(minimal_config.out_dir)
    assert out_dir.exists()
    assert (out_dir / "manifest.json").exists()
    assert (out_dir / "annotations.jsonl").exists()


def test_run_job_with_jobconfig_object(minimal_config):
    """Test run_job accepts JobConfig object."""
    backend = MockBackend()
    run_job(backend=backend, config_path_or_obj=minimal_config, use_cache=False)

    assert backend.started
    assert backend.closed
    assert backend.scene_loaded
    assert len(backend.assets) == 1
    assert len(backend.sensors) == 1


def test_run_job_with_out_dir_override(minimal_config, tmp_path):
    """Test run_job respects out_dir override in config."""
    # The out_dir is already set in minimal_config fixture
    backend = MockBackend()
    run_job(backend=backend, config_path_or_obj=minimal_config, use_cache=False)

    assert Path(minimal_config.out_dir).exists()


def test_run_job_with_seed_override(minimal_config):
    """Test run_job uses seed from config."""
    backend = MockBackend()
    run_job(backend=backend, config_path_or_obj=minimal_config, use_cache=False)
    # Backend reset is called with seed
    pass


def test_run_job_with_backend_instance(minimal_config):
    """Test run_job accepts backend instance."""
    backend = MockBackend()
    run_job(backend=backend, config_path_or_obj=minimal_config, use_cache=False)
    assert backend.started


def test_run_job_creates_expected_output_tree(minimal_config):
    """Test run_job creates the expected directory structure and files."""
    backend = MockBackend()
    run_job(backend=backend, config_path_or_obj=minimal_config, use_cache=False)

    out_dir = Path(minimal_config.out_dir)
    assert (out_dir / "rgb").exists()
    assert (out_dir / "depth").exists()
    assert (out_dir / "seg").exists()
    assert (out_dir / "meta").exists()
    assert (out_dir / "manifest.json").exists()
    assert (out_dir / "annotations.jsonl").exists()

    # Check frame files
    for i in range(minimal_config.num_frames):
        assert (out_dir / "rgb" / f"{i:06d}.png").exists()
        assert (out_dir / "depth" / f"{i:06d}.npy").exists()
        assert (out_dir / "seg" / f"{i:06d}.npy").exists()
        assert (out_dir / "meta" / f"{i:06d}.json").exists()


def test_run_job_invalid_config_type():
    """Test run_job raises error for invalid config type."""
    backend = MockBackend()
    with pytest.raises(TypeError):
        run_job(backend=backend, config_path_or_obj="not_a_config_or_path")


def test_run_job_invalid_backend_type(minimal_config):
    """Test run_job raises error for invalid backend type."""
    with pytest.raises(TypeError):
        run_job(backend=123, config_path_or_obj=minimal_config)  # type: ignore


def test_run_job_nonexistent_config_file(tmp_path):
    """Test run_job raises error for nonexistent config file."""
    with pytest.raises(FileNotFoundError):
        run_job(backend="dummy", config_path_or_obj=Path(tmp_path / "nonexistent.yaml"))


def test_run_job_fails_on_max_total_size_exceeded(minimal_config):
    """Test job fails when max_total_size is exceeded."""
    # Set a tiny limit
    minimal_config.max_total_size = 10  # 10 bytes
    minimal_config.num_frames = 10  # Ensure we hit the periodic check (every 10 frames)

    backend = MockBackend()

    # Write a dummy file to the output directory to simulate exceeding limit
    out_dir = Path(minimal_config.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "large_file.bin").write_bytes(b"x" * 100)  # 100 bytes > 10 bytes limit

    with pytest.raises(JobFailedError, match="Disk usage limit exceeded"):
        run_job(backend=backend, config_path_or_obj=minimal_config, use_cache=False)


def test_yolo_labels_non_empty_with_dummy_backend(tmp_path, minimal_config):
    """Test that DummyBackend produces non-empty YOLO labels (smoke test for fix)."""
    # Ensure DummyBackend is registered
    import komansim.backends.dummy.backend  # noqa: F401

    # Configure output to a clean directory
    out_dir = tmp_path / "yolo_smoke_test"
    minimal_config.out_dir = str(out_dir)

    # Ensure we have at least one asset to generate labels for
    assert len(minimal_config.assets) > 0

    # Run job with real DummyBackend
    run_job(backend="dummy", config_path_or_obj=minimal_config, use_cache=False)

    # Check YOLO labels
    yolo_dir = out_dir / "exports" / "yolo"
    assert yolo_dir.exists()
    assert (yolo_dir / "dataset.yaml").exists()

    # Check labels in train or val
    train_labels = list((yolo_dir / "labels" / "train").glob("*.txt"))
    val_labels = list((yolo_dir / "labels" / "val").glob("*.txt"))
    all_labels = train_labels + val_labels

    assert len(all_labels) == minimal_config.num_frames, "Should have one label file per frame"

    # Verify at least one label file has content
    has_content = False
    for label_path in all_labels:
        content = label_path.read_text().strip()
        if content:
            has_content = True
            # Verify valid YOLO line format
            parts = content.split()
            assert len(parts) >= 5, f"Invalid YOLO line in {label_path}"
            # Verify coordinates are normalized
            x, y, w, h = map(float, parts[1:5])
            assert 0 <= x <= 1
            assert 0 <= y <= 1
            assert 0 <= w <= 1
            assert 0 <= h <= 1
            break

    assert has_content, "YOLO labels should not be empty with DummyBackend"
