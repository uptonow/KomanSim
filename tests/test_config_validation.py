import pytest
from komansim.schemas.job_schema import JobConfig


def test_job_config_validates():
    cfg = JobConfig.model_validate(
        {
            "job_name": "t",
            "out_dir": "outputs/t",
            "num_frames": 1,
            "dt": 0.1,
            "headless": True,
            "width": 64,
            "height": 64,
            "scene": {"usd_path": None, "physics_dt": 1 / 60, "dome_light_intensity": 1500.0},
            "assets": [],
            "sensors": [],
            "randomization": {"random_xy": 0.1, "random_yaw_deg": 30.0},
        }
    )
    assert cfg.num_frames == 1


def _base_config():
    """Helper to create a base valid config."""
    return {
        "job_name": "test",
        "out_dir": "outputs/test",
        "num_frames": 10,
        "dt": 0.1,
        "headless": True,
        "width": 64,
        "height": 64,
        "scene": {"usd_path": None, "physics_dt": 1 / 60, "dome_light_intensity": 1500.0},
        "assets": [],
        "sensors": [
            {
                "name": "cam0",
                "type": "camera_rgb",
                "pose": {"p": [0.0, 0.0, 0.0], "q": [0.0, 0.0, 0.0, 1.0]},
                "intrinsics": {},
            }
        ],
        "randomization": {"random_xy": 0.1, "random_yaw_deg": 30.0},
    }


def test_config_within_limits():
    """Test that config passes validation when within all limits."""
    config = _base_config()
    config.update(
        {
            "max_frames": 100,
            "max_resolution": 10000,
            "max_modalities": 5,
            "max_total_size": 10_000_000,  # 10 MB
        }
    )
    cfg = JobConfig.model_validate(config)
    assert cfg.num_frames == 10
    assert cfg.max_frames == 100


def test_validation_fails_max_frames():
    """Test validation fails when num_frames exceeds max_frames."""
    config = _base_config()
    config.update(
        {
            "num_frames": 100,
            "max_frames": 50,
        }
    )
    with pytest.raises(ValueError, match="num_frames.*exceeds max_frames"):
        JobConfig.model_validate(config)


def test_validation_fails_max_resolution():
    """Test validation fails when resolution exceeds max_resolution."""
    config = _base_config()
    config.update(
        {
            "width": 200,
            "height": 200,  # 40,000 pixels
            "max_resolution": 10_000,  # Only 10,000 pixels allowed
        }
    )
    with pytest.raises(ValueError, match="Resolution.*exceeds max_resolution"):
        JobConfig.model_validate(config)


def test_validation_fails_max_modalities():
    """Test validation fails when number of unique sensor types exceeds max_modalities."""
    config = _base_config()
    config["sensors"] = [
        {
            "name": "cam0",
            "type": "camera_rgb",
            "pose": {"p": [0.0, 0.0, 0.0], "q": [0.0, 0.0, 0.0, 1.0]},
            "intrinsics": {},
        },
        {
            "name": "cam1",
            "type": "camera_depth",
            "pose": {"p": [0.0, 0.0, 0.0], "q": [0.0, 0.0, 0.0, 1.0]},
            "intrinsics": {},
        },
        {
            "name": "cam2",
            "type": "camera_segmentation",
            "pose": {"p": [0.0, 0.0, 0.0], "q": [0.0, 0.0, 0.0, 1.0]},
            "intrinsics": {},
        },
    ]
    config["max_modalities"] = 2  # Only 2 unique types allowed, but we have 3
    with pytest.raises(ValueError, match="Number of unique sensor types.*exceeds max_modalities"):
        JobConfig.model_validate(config)


def test_validation_fails_max_total_size():
    """Test validation fails when estimated total size exceeds max_total_size."""
    config = _base_config()
    config.update(
        {
            "num_frames": 1000,
            "width": 640,
            "height": 480,  # 307,200 pixels per frame
            "max_total_size": 100_000,  # Only 100 KB allowed
        }
    )
    # Estimated: 1000 frames * 307200 pixels * 3 bytes (RGB) = 921,600,000 bytes
    with pytest.raises(ValueError, match="Estimated total size.*exceeds max_total_size"):
        JobConfig.model_validate(config)


def test_validation_fails_multiple_limits():
    """Test validation fails with clear error messages for multiple limit violations."""
    config = _base_config()
    config.update(
        {
            "num_frames": 200,  # Exceeds max_frames
            "width": 200,
            "height": 200,  # Exceeds max_resolution
            "max_frames": 100,
            "max_resolution": 10_000,
        }
    )
    with pytest.raises(ValueError) as exc_info:
        JobConfig.model_validate(config)
    error_msg = str(exc_info.value)
    assert "num_frames" in error_msg
    assert "max_frames" in error_msg
    assert "Resolution" in error_msg
    assert "max_resolution" in error_msg


def test_validation_passes_when_limits_not_set():
    """Test that validation passes when limits are None (not enforced)."""
    config = _base_config()
    config.update(
        {
            "num_frames": 10000,
            "width": 1920,
            "height": 1080,
            "max_frames": None,
            "max_resolution": None,
            "max_modalities": None,
            "max_total_size": None,
        }
    )
    cfg = JobConfig.model_validate(config)
    assert cfg.num_frames == 10000


def test_size_estimation_with_multiple_modalities():
    """Test that size estimation accounts for multiple modalities correctly."""
    config = _base_config()
    config["sensors"] = [
        {
            "name": "cam0",
            "type": "camera_rgb",
            "pose": {"p": [0.0, 0.0, 0.0], "q": [0.0, 0.0, 0.0, 1.0]},
            "intrinsics": {},
        },
        {
            "name": "cam1",
            "type": "camera_depth",
            "pose": {"p": [0.0, 0.0, 0.0], "q": [0.0, 0.0, 0.0, 1.0]},
            "intrinsics": {},
        },
    ]
    config.update(
        {
            "num_frames": 100,
            "width": 100,
            "height": 100,  # 10,000 pixels
            "max_total_size": 1_000_000,  # 1 MB
        }
    )
    # Estimated: 100 frames * 10,000 pixels * (3 RGB + 4 depth) = 7,000,000 bytes
    with pytest.raises(ValueError, match="Estimated total size.*exceeds max_total_size"):
        JobConfig.model_validate(config)


def test_validation_fails_negative_limits():
    """Test that negative resource limits are rejected."""
    config = _base_config()
    config["max_frames"] = -1
    with pytest.raises(ValueError, match="Resource limits must be > 0 if set"):
        JobConfig.model_validate(config)
