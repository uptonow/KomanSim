"""Tests for cache hit behavior in simdata run command."""

import json
from pathlib import Path

import yaml

from komansim.registry.local_registry import LocalRegistry
from komansim.runtime.run_job import run_job
from komansim.runtime.result import RunResult
from komansim.schemas.job_schema import JobConfig
from komansim.utils.hashing import config_hash


def test_cache_hit_skips_generation(tmp_path: Path, monkeypatch):
    """Test that cache hit skips generation and returns early."""
    # Mock home directory to use tmp_path
    fake_home = tmp_path / "fake_home"
    fake_home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: fake_home)

    # Create a config
    config_file = tmp_path / "test_config.yaml"
    config_data = {
        "job_name": "cache_test",
        "out_dir": str(tmp_path / "outputs" / "cache_test"),
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

    # First, run without cache to generate and register
    result1 = run_job(config_path_or_obj=config_file, backend="dummy", use_cache=False)

    # Verify result is RunResult
    assert isinstance(result1, RunResult)
    assert result1.cache_hit is False
    assert result1.status == "succeeded"
    assert result1.backend == "dummy"
    assert result1.package_path
    assert Path(result1.package_path).exists()

    # Verify output was created
    out_dir = tmp_path / "outputs" / "cache_test"
    assert out_dir.exists()
    assert (out_dir / "rgb" / "000000.png").exists()

    # Verify it's registered in registry
    registry = LocalRegistry()
    cfg = JobConfig.model_validate(config_data)
    # Include backend in hash, matching the actual code behavior
    hash_input = {**cfg.model_dump(), "_backend": "dummy"}
    hash_value = config_hash(hash_input)
    entry = registry.find_by_config_hash(hash_value)
    assert entry is not None
    assert entry["package_path"] == result1.package_path
    assert result1.config_hash == hash_value
    assert result1.dataset_id == entry["dataset_id"]

    # Now run with cache - should skip generation
    # We need to track if backend.start() was called
    # Since we can't easily mock that, we'll check that the output directory
    # wasn't modified (timestamps)
    import time

    time.sleep(0.1)  # Ensure timestamp difference

    # Get modification time of first RGB file
    rgb_file = out_dir / "rgb" / "000000.png"
    original_mtime = rgb_file.stat().st_mtime

    # Run with cache - should return RunResult with cache_hit=True
    result2 = run_job(config_path_or_obj=config_file, backend="dummy", use_cache=True)

    # Verify result is RunResult with cache_hit=True
    assert isinstance(result2, RunResult)
    assert result2.cache_hit is True
    assert result2.status == "succeeded"
    assert result2.backend == "dummy"
    assert result2.package_path == result1.package_path
    assert Path(result2.package_path).exists()
    assert result2.config_hash == hash_value
    assert result2.dataset_id == result1.dataset_id

    # Verify file wasn't regenerated (mtime unchanged)
    # Note: This is a weak test, but it's the best we can do without more mocking
    new_mtime = rgb_file.stat().st_mtime
    assert new_mtime == original_mtime, "File should not have been regenerated"


def test_cache_miss_runs_generation(tmp_path: Path, monkeypatch):
    """Test that cache miss runs generation normally."""
    # Mock home directory
    fake_home = tmp_path / "fake_home"
    fake_home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: fake_home)

    # Create a config
    config_file = tmp_path / "test_config.yaml"
    config_data = {
        "job_name": "cache_miss_test",
        "out_dir": str(tmp_path / "outputs" / "cache_miss_test"),
        "seed": 42,
        "num_frames": 2,
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

    # Run with cache - should generate since no cache entry exists
    result = run_job(config_path_or_obj=config_file, backend="dummy", use_cache=True)

    # Verify result is RunResult with cache_hit=False
    assert isinstance(result, RunResult)
    assert result.cache_hit is False
    assert result.status == "succeeded"
    assert result.backend == "dummy"
    assert result.package_path
    assert Path(result.package_path).exists()

    # Verify output was created
    out_dir = tmp_path / "outputs" / "cache_miss_test"
    assert out_dir.exists()
    assert (out_dir / "rgb" / "000000.png").exists()
    assert (out_dir / "rgb" / "000001.png").exists()

    # Verify manifest has cache_hit=False
    manifest_path = out_dir / "manifest.json"
    assert manifest_path.exists()
    manifest = json.loads(manifest_path.read_text())
    assert manifest["cache_hit"] is False


def test_cache_hit_with_missing_package(tmp_path: Path, monkeypatch):
    """Test that cache miss occurs if package_path doesn't exist."""
    # Mock home directory
    fake_home = tmp_path / "fake_home"
    fake_home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: fake_home)

    # Create registry and register an entry with non-existent package
    registry = LocalRegistry()
    config_dict = {"job_name": "missing_package_test", "num_frames": 10}
    # Compute hashes using new semantics
    from komansim.utils.hashing import canonicalize, dataset_hash
    from komansim.pipeline.manifest import _get_simdata_version

    canonical_jobspec = canonicalize(config_dict)
    simdata_version = _get_simdata_version()
    dataset_hash_value = dataset_hash(canonical_jobspec, "dummy", simdata_version)
    # Also compute old config_hash for backwards compatibility
    hash_input = {**config_dict, "_backend": "dummy"}
    old_hash_value = config_hash(hash_input)
    registry.register(
        dataset_hash=dataset_hash_value,
        backend="dummy",
        out_dir=str(tmp_path / "outputs" / "missing"),
        package_path=str(tmp_path / "nonexistent.zip"),
        config_hash=old_hash_value,  # For backwards compatibility
    )

    # Create config matching the hash
    config_file = tmp_path / "test_config.yaml"
    config_data = {
        "job_name": "missing_package_test",
        "out_dir": str(tmp_path / "outputs" / "missing_package_test"),
        "num_frames": 10,
        "dt": 0.1,
        "headless": True,
        "width": 64,
        "height": 64,
    }
    config_file.write_text(yaml.safe_dump(config_data), encoding="utf-8")

    # Run with cache - should generate since package doesn't exist (cache miss)
    result = run_job(config_path_or_obj=config_file, backend="dummy", use_cache=True)

    # Verify result is RunResult with cache_hit=False (treated as cache miss)
    assert isinstance(result, RunResult)
    assert result.cache_hit is False
    assert result.status == "succeeded"
    assert result.backend == "dummy"
    assert result.package_path
    assert Path(result.package_path).exists()

    # Verify output was created (cache was missed)
    out_dir = tmp_path / "outputs" / "missing_package_test"
    assert out_dir.exists()
    assert (out_dir / "rgb" / "000000.png").exists()


def test_manifest_includes_cache_hit_field(tmp_path: Path, monkeypatch):
    """Test that manifest includes cache_hit field set to False."""
    # Mock home directory
    fake_home = tmp_path / "fake_home"
    fake_home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: fake_home)

    # Create a config
    config_file = tmp_path / "test_config.yaml"
    config_data = {
        "job_name": "manifest_cache_test",
        "out_dir": str(tmp_path / "outputs" / "manifest_cache_test"),
        "seed": 42,
        "num_frames": 1,
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
    result = run_job(config_path_or_obj=config_file, backend="dummy", use_cache=False)

    # Verify result is RunResult
    assert isinstance(result, RunResult)
    assert result.cache_hit is False
    assert result.status == "succeeded"

    # Verify manifest has cache_hit field
    out_dir = tmp_path / "outputs" / "manifest_cache_test"
    manifest_path = out_dir / "manifest.json"
    assert manifest_path.exists()

    manifest = json.loads(manifest_path.read_text())
    assert "cache_hit" in manifest
    assert manifest["cache_hit"] is False


def test_registry_registers_after_generation(tmp_path: Path, monkeypatch):
    """Test that registry entry is created after successful generation."""
    # Mock home directory
    fake_home = tmp_path / "fake_home"
    fake_home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: fake_home)

    # Create a config
    config_file = tmp_path / "test_config.yaml"
    config_data = {
        "job_name": "registry_test",
        "out_dir": str(tmp_path / "outputs" / "registry_test"),
        "seed": 42,
        "num_frames": 1,
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
    result = run_job(config_path_or_obj=config_file, backend="dummy", use_cache=False)

    # Verify result is RunResult
    assert isinstance(result, RunResult)
    assert result.cache_hit is False
    assert result.status == "succeeded"
    assert result.backend == "dummy"

    # Verify registry entry was created
    registry = LocalRegistry()
    cfg = JobConfig.model_validate(config_data)
    # Include backend in hash, matching the actual code behavior
    hash_input = {**cfg.model_dump(), "_backend": "dummy"}
    hash_value = config_hash(hash_input)
    entry = registry.find_by_config_hash(hash_value)

    assert entry is not None
    assert entry["backend"] == "dummy"
    assert entry["out_dir"] == str(tmp_path / "outputs" / "registry_test")
    assert entry["package_path"] is not None
    assert Path(entry["package_path"]).exists()

    # Verify result matches registry entry
    assert result.config_hash == hash_value
    assert result.dataset_id == entry["dataset_id"]
    assert result.package_path == entry["package_path"]


def test_manifest_includes_jobspec_and_dataset_hashes(tmp_path: Path, monkeypatch):
    """Test that manifest includes both jobspec_hash and dataset_hash."""
    from komansim.utils.hashing import canonicalize, jobspec_hash, dataset_hash
    from komansim.pipeline.manifest import _get_simdata_version

    # Mock home directory
    fake_home = tmp_path / "fake_home"
    fake_home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: fake_home)

    # Create a config
    config_file = tmp_path / "test_config.yaml"
    config_data = {
        "job_name": "hash_test",
        "out_dir": str(tmp_path / "outputs" / "hash_test"),
        "seed": 42,
        "num_frames": 1,
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
    result = run_job(config_path_or_obj=config_file, backend="dummy", use_cache=False)

    # Verify result is RunResult
    assert isinstance(result, RunResult)
    assert result.status == "succeeded"

    # Verify manifest includes both hashes
    out_dir = tmp_path / "outputs" / "hash_test"
    manifest_path = out_dir / "manifest.json"
    assert manifest_path.exists()

    manifest = json.loads(manifest_path.read_text())
    assert "jobspec_hash" in manifest
    assert "dataset_hash" in manifest

    # Verify hashes are computed correctly
    cfg = JobConfig.model_validate(config_data)
    config_dict = cfg.model_dump()
    canonical_jobspec = canonicalize(config_dict)
    simdata_version = _get_simdata_version()

    expected_jobspec_hash = jobspec_hash(canonical_jobspec)
    expected_dataset_hash = dataset_hash(canonical_jobspec, "dummy", simdata_version)

    assert manifest["jobspec_hash"] == expected_jobspec_hash
    assert manifest["dataset_hash"] == expected_dataset_hash


def test_cache_uses_dataset_hash(tmp_path: Path, monkeypatch):
    """Test that cache lookup uses dataset_hash."""
    from komansim.utils.hashing import canonicalize, dataset_hash
    from komansim.pipeline.manifest import _get_simdata_version

    # Mock home directory
    fake_home = tmp_path / "fake_home"
    fake_home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: fake_home)

    # Create a config
    config_file = tmp_path / "test_config.yaml"
    config_data = {
        "job_name": "dataset_hash_cache_test",
        "out_dir": str(tmp_path / "outputs" / "dataset_hash_cache_test"),
        "seed": 42,
        "num_frames": 1,
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

    # First run - generate and register
    result1 = run_job(config_path_or_obj=config_file, backend="dummy", use_cache=False)
    assert result1.cache_hit is False
    assert result1.status == "succeeded"

    # Verify registry entry has dataset_hash
    registry = LocalRegistry()
    cfg = JobConfig.model_validate(config_data)
    config_dict = cfg.model_dump()
    canonical_jobspec = canonicalize(config_dict)
    simdata_version = _get_simdata_version()
    expected_dataset_hash = dataset_hash(canonical_jobspec, "dummy", simdata_version)

    entry = registry.find_by_dataset_hash(expected_dataset_hash)
    assert entry is not None
    assert entry["dataset_hash"] == expected_dataset_hash
    assert entry["dataset_id"] == result1.dataset_id

    # Second run with cache - should use dataset_hash for lookup
    result2 = run_job(config_path_or_obj=config_file, backend="dummy", use_cache=True)
    assert result2.cache_hit is True
    assert result2.status == "succeeded"
    assert result2.dataset_id == result1.dataset_id
    assert result2.package_path == result1.package_path
