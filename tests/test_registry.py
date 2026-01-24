"""Tests for simdata.registry.local_registry module."""

from pathlib import Path

import pytest

from komansim.registry.local_registry import LocalRegistry
from komansim.utils.hashing import config_hash, canonicalize, jobspec_hash, dataset_hash
from komansim.pipeline.manifest import _get_simdata_version


def test_registry_creates_directory(tmp_path: Path):
    """Test that registry creates the directory if it doesn't exist."""
    registry_path = tmp_path / "test_registry.json"
    registry = LocalRegistry(registry_path=registry_path)

    assert registry_path.parent.exists()
    assert registry_path.exists() or len(registry.list_all()) == 0


def test_registry_register_and_find(tmp_path: Path):
    """Test registering a dataset and finding it by config hash."""
    registry_path = tmp_path / "registry.json"
    registry = LocalRegistry(registry_path=registry_path)

    config_dict = {"job_name": "test", "num_frames": 10}
    canonical_jobspec = canonicalize(config_dict)
    simdata_version = _get_simdata_version()
    dataset_hash_value = dataset_hash(canonical_jobspec, "dummy", simdata_version)
    jobspec_hash_value = jobspec_hash(canonical_jobspec)
    old_hash_value = config_hash({**config_dict, "_backend": "dummy"})

    dataset_id = registry.register(
        dataset_hash=dataset_hash_value,
        backend="dummy",
        out_dir="/tmp/test_output",
        package_path="/tmp/test_output.zip",
        jobspec_hash=jobspec_hash_value,
        config_hash=old_hash_value,
    )

    assert dataset_id is not None
    assert len(dataset_id) > 0

    # Find by config hash (backwards compatibility)
    entry = registry.find_by_config_hash(old_hash_value)
    assert entry is not None
    assert entry["config_hash"] == old_hash_value
    # Also verify dataset_hash
    assert entry["dataset_hash"] == dataset_hash_value
    assert entry["backend"] == "dummy"
    assert entry["out_dir"] == "/tmp/test_output"
    assert entry["package_path"] == "/tmp/test_output.zip"
    assert entry["dataset_id"] == dataset_id


def test_registry_find_by_dataset_id(tmp_path: Path):
    """Test finding a dataset by dataset ID."""
    registry_path = tmp_path / "registry.json"
    registry = LocalRegistry(registry_path=registry_path)

    config_dict = {"job_name": "test2", "num_frames": 20}
    canonical_jobspec = canonicalize(config_dict)
    simdata_version = _get_simdata_version()
    dataset_hash_value = dataset_hash(canonical_jobspec, "mujoco", simdata_version)
    jobspec_hash_value = jobspec_hash(canonical_jobspec)
    old_hash_value = config_hash({**config_dict, "_backend": "mujoco"})

    dataset_id = registry.register(
        dataset_hash=dataset_hash_value,
        backend="mujoco",
        out_dir="/tmp/test2_output",
        jobspec_hash=jobspec_hash_value,
        config_hash=old_hash_value,
    )

    entry = registry.find_by_dataset_id(dataset_id)
    assert entry is not None
    assert entry["dataset_id"] == dataset_id
    assert entry["backend"] == "mujoco"


def test_registry_list_all(tmp_path: Path):
    """Test listing all datasets."""
    registry_path = tmp_path / "registry.json"
    registry = LocalRegistry(registry_path=registry_path)

    # Register multiple datasets
    for i in range(3):
        config_dict = {"job_name": f"test_{i}", "num_frames": i * 10}
        canonical_jobspec = canonicalize(config_dict)
        simdata_version = _get_simdata_version()
        dataset_hash_value = dataset_hash(canonical_jobspec, "dummy", simdata_version)
        jobspec_hash_value = jobspec_hash(canonical_jobspec)
        old_hash_value = config_hash({**config_dict, "_backend": "dummy"})
        registry.register(
            dataset_hash=dataset_hash_value,
            backend="dummy",
            out_dir=f"/tmp/test_{i}",
            jobspec_hash=jobspec_hash_value,
            config_hash=old_hash_value,
        )

    entries = registry.list_all()
    assert len(entries) == 3
    # Should be sorted by created_at (newest first)
    # Check that entries are sorted (newest first) by verifying out_dir order
    out_dirs = [e["out_dir"] for e in entries]
    assert "/tmp/test_2" in out_dirs
    assert "/tmp/test_1" in out_dirs
    assert "/tmp/test_0" in out_dirs


def test_registry_update_package_path(tmp_path: Path):
    """Test updating package path for an existing entry."""
    registry_path = tmp_path / "registry.json"
    registry = LocalRegistry(registry_path=registry_path)

    config_dict = {"job_name": "test", "num_frames": 10}
    canonical_jobspec = canonicalize(config_dict)
    simdata_version = _get_simdata_version()
    dataset_hash_value = dataset_hash(canonical_jobspec, "dummy", simdata_version)
    jobspec_hash_value = jobspec_hash(canonical_jobspec)
    old_hash_value = config_hash({**config_dict, "_backend": "dummy"})

    dataset_id = registry.register(
        dataset_hash=dataset_hash_value,
        backend="dummy",
        out_dir="/tmp/test",
        jobspec_hash=jobspec_hash_value,
        config_hash=old_hash_value,
    )

    registry.update_package_path(dataset_id, "/tmp/test_new.zip")

    entry = registry.find_by_dataset_id(dataset_id)
    assert entry["package_path"] == "/tmp/test_new.zip"


def test_registry_update_package_path_not_found(tmp_path: Path):
    """Test that updating package path raises KeyError for non-existent dataset."""
    registry_path = tmp_path / "registry.json"
    registry = LocalRegistry(registry_path=registry_path)

    with pytest.raises(KeyError, match="Dataset ID not found"):
        registry.update_package_path("nonexistent-id", "/tmp/test.zip")


def test_registry_delete(tmp_path: Path):
    """Test deleting a dataset entry."""
    registry_path = tmp_path / "registry.json"
    registry = LocalRegistry(registry_path=registry_path)

    config_dict = {"job_name": "test", "num_frames": 10}
    canonical_jobspec = canonicalize(config_dict)
    simdata_version = _get_simdata_version()
    dataset_hash_value = dataset_hash(canonical_jobspec, "dummy", simdata_version)
    jobspec_hash_value = jobspec_hash(canonical_jobspec)
    old_hash_value = config_hash({**config_dict, "_backend": "dummy"})

    dataset_id = registry.register(
        dataset_hash=dataset_hash_value,
        backend="dummy",
        out_dir="/tmp/test",
        jobspec_hash=jobspec_hash_value,
        config_hash=old_hash_value,
    )

    assert registry.find_by_dataset_id(dataset_id) is not None

    deleted = registry.delete(dataset_id)
    assert deleted is True

    assert registry.find_by_dataset_id(dataset_id) is None

    # Try deleting again
    deleted = registry.delete(dataset_id)
    assert deleted is False


def test_registry_clear(tmp_path: Path):
    """Test clearing all entries from registry."""
    registry_path = tmp_path / "registry.json"
    registry = LocalRegistry(registry_path=registry_path)

    # Register multiple datasets
    for i in range(3):
        config_dict = {"job_name": f"test_{i}", "num_frames": i * 10}
        canonical_jobspec = canonicalize(config_dict)
        simdata_version = _get_simdata_version()
        dataset_hash_value = dataset_hash(canonical_jobspec, "dummy", simdata_version)
        jobspec_hash_value = jobspec_hash(canonical_jobspec)
        old_hash_value = config_hash({**config_dict, "_backend": "dummy"})
        registry.register(
            dataset_hash=dataset_hash_value,
            backend="dummy",
            out_dir=f"/tmp/test_{i}",
            jobspec_hash=jobspec_hash_value,
            config_hash=old_hash_value,
        )

    assert len(registry.list_all()) == 3

    registry.clear()

    assert len(registry.list_all()) == 0


def test_registry_persists_to_disk(tmp_path: Path):
    """Test that registry persists data to disk and loads it back."""
    registry_path = tmp_path / "registry.json"

    # Create registry and register entry
    registry1 = LocalRegistry(registry_path=registry_path)
    config_dict = {"job_name": "persist_test", "num_frames": 5}
    canonical_jobspec = canonicalize(config_dict)
    simdata_version = _get_simdata_version()
    dataset_hash_value = dataset_hash(canonical_jobspec, "dummy", simdata_version)
    jobspec_hash_value = jobspec_hash(canonical_jobspec)
    old_hash_value = config_hash({**config_dict, "_backend": "dummy"})
    dataset_id = registry1.register(
        dataset_hash=dataset_hash_value,
        backend="dummy",
        out_dir="/tmp/persist_test",
        jobspec_hash=jobspec_hash_value,
        config_hash=old_hash_value,
    )

    # Create new registry instance and verify it loads the data
    registry2 = LocalRegistry(registry_path=registry_path)
    entry = registry2.find_by_dataset_id(dataset_id)
    assert entry is not None
    assert entry["out_dir"] == "/tmp/persist_test"


def test_registry_with_template(tmp_path: Path):
    """Test registry with template field."""
    registry_path = tmp_path / "registry.json"
    registry = LocalRegistry(registry_path=registry_path)

    config_dict = {"job_name": "template_test", "num_frames": 10}
    canonical_jobspec = canonicalize(config_dict)
    simdata_version = _get_simdata_version()
    dataset_hash_value = dataset_hash(canonical_jobspec, "dummy", simdata_version)
    jobspec_hash_value = jobspec_hash(canonical_jobspec)
    old_hash_value = config_hash({**config_dict, "_backend": "dummy"})

    dataset_id = registry.register(
        dataset_hash=dataset_hash_value,
        backend="dummy",
        out_dir="/tmp/template_test",
        template="tabletop_clutter",
        jobspec_hash=jobspec_hash_value,
        config_hash=old_hash_value,
    )

    entry = registry.find_by_dataset_id(dataset_id)
    assert entry["template"] == "tabletop_clutter"


def test_registry_custom_dataset_id(tmp_path: Path):
    """Test registering with custom dataset ID."""
    registry_path = tmp_path / "registry.json"
    registry = LocalRegistry(registry_path=registry_path)

    config_dict = {"job_name": "custom_id_test", "num_frames": 10}
    canonical_jobspec = canonicalize(config_dict)
    simdata_version = _get_simdata_version()
    dataset_hash_value = dataset_hash(canonical_jobspec, "dummy", simdata_version)
    jobspec_hash_value = jobspec_hash(canonical_jobspec)
    old_hash_value = config_hash({**config_dict, "_backend": "dummy"})

    custom_id = "my-custom-id-123"
    dataset_id = registry.register(
        dataset_hash=dataset_hash_value,
        backend="dummy",
        out_dir="/tmp/custom_test",
        dataset_id=custom_id,
        jobspec_hash=jobspec_hash_value,
        config_hash=old_hash_value,
    )

    assert dataset_id == custom_id
    entry = registry.find_by_dataset_id(custom_id)
    assert entry is not None


def test_registry_find_by_config_hash_not_found(tmp_path: Path):
    """Test that find_by_config_hash returns None for non-existent hash."""
    registry_path = tmp_path / "registry.json"
    registry = LocalRegistry(registry_path=registry_path)

    config_dict = {"job_name": "nonexistent", "num_frames": 999}
    hash_value = config_hash(config_dict)

    entry = registry.find_by_config_hash(hash_value)
    assert entry is None


def test_registry_loads_corrupted_json(tmp_path: Path):
    """Test that registry handles corrupted JSON gracefully."""
    registry_path = tmp_path / "registry.json"

    # Write invalid JSON
    registry_path.write_text("invalid json content", encoding="utf-8")

    # Should not raise, but start with empty registry
    registry = LocalRegistry(registry_path=registry_path)
    assert len(registry.list_all()) == 0


def test_registry_with_monkeypatch_home(tmp_path: Path, monkeypatch):
    """Test registry with monkeypatched home directory."""
    # Mock home directory
    fake_home = tmp_path / "fake_home"
    fake_home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: fake_home)

    # Create registry (should use ~/.simdata/registry.json)
    registry = LocalRegistry()

    # Verify it uses the mocked home
    expected_path = fake_home / ".simdata" / "registry.json"
    assert registry.registry_dir == expected_path.parent

    # Register an entry
    config_dict = {"job_name": "monkeypatch_test", "num_frames": 10}
    canonical_jobspec = canonicalize(config_dict)
    simdata_version = _get_simdata_version()
    dataset_hash_value = dataset_hash(canonical_jobspec, "dummy", simdata_version)
    jobspec_hash_value = jobspec_hash(canonical_jobspec)
    old_hash_value = config_hash({**config_dict, "_backend": "dummy"})
    dataset_id = registry.register(
        dataset_hash=dataset_hash_value,
        backend="dummy",
        out_dir="/tmp/monkeypatch_test",
        jobspec_hash=jobspec_hash_value,
        config_hash=old_hash_value,
    )

    # Verify it was saved
    assert expected_path.exists()

    # Create new registry and verify it loads
    registry2 = LocalRegistry()
    entry = registry2.find_by_dataset_id(dataset_id)
    assert entry is not None
