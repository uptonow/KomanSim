"""Smoke tests for the SDK entry point."""

from pathlib import Path

import yaml

from komansim import run, stats, validate_config


def test_sdk_validate_config(tmp_path: Path):
    """Test validate_config function."""
    # Create a test config file
    config_file = tmp_path / "test_config.yaml"
    config_data = {
        "job_name": "sdk_test",
        "out_dir": str(tmp_path / "outputs" / "sdk_test"),
        "seed": 42,
        "num_frames": 5,
        "dt": 0.1,
        "headless": True,
        "width": 64,
        "height": 64,
        "scene": {"usd_path": None, "physics_dt": 0.01, "dome_light_intensity": 1000.0},
        "assets": [],
        "sensors": [
            {
                "name": "cam0",
                "type": "camera_rgb",
                "pose": {"p": [1.0, 1.0, 1.0], "q": [0.0, 0.0, 0.0, 1.0]},
                "intrinsics": {"fx": 32, "fy": 32, "cx": 32, "cy": 32},
            }
        ],
        "randomization": {"random_xy": 0.1, "random_yaw_deg": 90.0},
    }
    config_file.write_text(yaml.safe_dump(config_data), encoding="utf-8")

    # Validate from file
    config = validate_config(config_file)
    assert config.job_name == "sdk_test"
    assert config.num_frames == 5

    # Validate from dict
    config2 = validate_config(config_data)
    assert config2.job_name == "sdk_test"


def test_sdk_run_dummy(tmp_path: Path, monkeypatch):
    """Test run function with dummy backend."""
    # Mock home directory
    fake_home = tmp_path / "fake_home"
    fake_home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: fake_home)

    # Create a test config
    config_file = tmp_path / "test_config.yaml"
    config_data = {
        "job_name": "sdk_run_test",
        "out_dir": str(tmp_path / "outputs" / "sdk_run_test"),
        "seed": 42,
        "num_frames": 3,
        "dt": 0.1,
        "headless": True,
        "width": 64,
        "height": 64,
        "scene": {"usd_path": None, "physics_dt": 0.01, "dome_light_intensity": 1000.0},
        "assets": [],
        "sensors": [
            {
                "name": "cam0",
                "type": "camera_rgb",
                "pose": {"p": [1.0, 1.0, 1.0], "q": [0.0, 0.0, 0.0, 1.0]},
                "intrinsics": {"fx": 32, "fy": 32, "cx": 32, "cy": 32},
            }
        ],
        "randomization": {"random_xy": 0.1, "random_yaw_deg": 90.0},
    }
    config_file.write_text(yaml.safe_dump(config_data), encoding="utf-8")

    # Run job
    result = run(
        config_file,
        backend="dummy",
        cache=False,
        out_dir=tmp_path / "outputs" / "sdk_run_test",
    )

    # Verify result
    assert result.status == "succeeded"
    assert result.cache_hit is False
    assert result.backend == "dummy"
    assert result.dataset_id is not None

    # Verify output directory exists
    out_dir = tmp_path / "outputs" / "sdk_run_test"
    assert out_dir.exists()
    assert (out_dir / "rgb").exists()
    assert (out_dir / "manifest.json").exists()

    # Verify manifest includes hashes
    import json

    manifest_path = out_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert "jobspec_hash" in manifest
    assert "dataset_hash" in manifest
    assert manifest["jobspec_hash"] is not None
    assert manifest["dataset_hash"] is not None


def test_sdk_stats(tmp_path: Path, monkeypatch):
    """Test stats function."""
    # Mock home directory
    fake_home = tmp_path / "fake_home"
    fake_home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: fake_home)

    # Create and run a job first
    config_file = tmp_path / "test_config.yaml"
    config_data = {
        "job_name": "sdk_stats_test",
        "out_dir": str(tmp_path / "outputs" / "sdk_stats_test"),
        "seed": 42,
        "num_frames": 5,
        "dt": 0.1,
        "headless": True,
        "width": 64,
        "height": 64,
        "scene": {"usd_path": None, "physics_dt": 0.01, "dome_light_intensity": 1000.0},
        "assets": [],
        "sensors": [
            {
                "name": "cam0",
                "type": "camera_rgb",
                "pose": {"p": [1.0, 1.0, 1.0], "q": [0.0, 0.0, 0.0, 1.0]},
                "intrinsics": {"fx": 32, "fy": 32, "cx": 32, "cy": 32},
            }
        ],
        "randomization": {"random_xy": 0.1, "random_yaw_deg": 90.0},
    }
    config_file.write_text(yaml.safe_dump(config_data), encoding="utf-8")

    # Run job
    result = run(config_file, backend="dummy", cache=False)
    assert result.status == "succeeded"

    # Get stats
    out_dir = tmp_path / "outputs" / "sdk_stats_test"
    stats_dict = stats(out_dir)

    # Verify stats
    assert stats_dict["num_frames"] == 5
    assert stats_dict["backend"] == "dummy"
    assert stats_dict["dataset_hash"] is not None
    assert stats_dict["jobspec_hash"] is not None
    assert stats_dict["total_files"] > 0
    assert stats_dict["total_bytes"] > 0
    assert stats_dict["cache_hit"] is False
