"""Tests for simdata.pipeline.manifest module."""

import json
import tempfile
from pathlib import Path


from komansim.backends.dummy.backend import DummyBackend
from komansim.pipeline.manifest import (
    build_manifest,
    collect_file_inventory,
    write_manifest,
)
from komansim.schemas.job_schema import JobConfig


def test_collect_file_inventory_empty_dir(tmp_path: Path):
    """Test collect_file_inventory with empty directory."""
    files, by_suffix, total_files, total_bytes = collect_file_inventory(tmp_path)

    assert files == []
    assert by_suffix == {}
    assert total_files == 0
    assert total_bytes == 0


def test_collect_file_inventory_stable_ordering(tmp_path: Path):
    """Test that collect_file_inventory returns files in stable sorted order."""
    # Create files in non-alphabetical order
    (tmp_path / "z_file.txt").write_text("content")
    (tmp_path / "a_file.txt").write_text("content")
    (tmp_path / "m_file.txt").write_text("content")

    files, _, _, _ = collect_file_inventory(tmp_path)

    # Should be sorted by path
    paths = [f["path"] for f in files]
    assert paths == sorted(paths)
    assert paths[0] == "a_file.txt"
    assert paths[1] == "m_file.txt"
    assert paths[2] == "z_file.txt"


def test_collect_file_inventory_counts_by_suffix(tmp_path: Path):
    """Test that collect_file_inventory counts files by suffix."""
    (tmp_path / "file1.png").write_text("content")
    (tmp_path / "file2.png").write_text("content")
    (tmp_path / "file3.json").write_text("content")
    (tmp_path / "file4.npy").write_text("content")
    (tmp_path / "subdir").mkdir(parents=True)
    (tmp_path / "subdir" / "file5.png").write_text("content")

    _, by_suffix, total_files, _ = collect_file_inventory(tmp_path)

    assert by_suffix[".png"] == 3
    assert by_suffix[".json"] == 1
    assert by_suffix[".npy"] == 1
    assert total_files == 5


def test_collect_file_inventory_total_bytes(tmp_path: Path):
    """Test that collect_file_inventory calculates total bytes correctly."""
    (tmp_path / "small.txt").write_text("x" * 10)
    (tmp_path / "large.txt").write_text("y" * 100)

    files, _, total_files, total_bytes = collect_file_inventory(tmp_path)

    assert total_files == 2
    assert total_bytes == 110
    # Files are sorted by path, so order may vary
    file_sizes = {f["path"]: f["bytes"] for f in files}
    assert file_sizes["large.txt"] == 100
    assert file_sizes["small.txt"] == 10


def test_build_manifest_structure(tmp_path: Path):
    """Test that build_manifest produces correct structure."""
    cfg = JobConfig(
        job_name="test_job",
        out_dir=str(tmp_path),
        num_frames=1,
        dt=0.1,
        headless=True,
        width=64,
        height=64,
    )
    backend = DummyBackend()

    # Create some output files
    (tmp_path / "rgb" / "000000.png").parent.mkdir(parents=True)
    (tmp_path / "rgb" / "000000.png").write_bytes(b"fake image")
    (tmp_path / "meta" / "000000.json").parent.mkdir(parents=True)
    (tmp_path / "meta" / "000000.json").write_text('{"frame": 0}')

    manifest = build_manifest(cfg, backend, "dummy", tmp_path)

    # Check required fields
    assert manifest["schema_version"] == "manifest.v1"
    assert "run_id" in manifest
    assert "created_at_utc" in manifest
    assert "config_hash" in manifest
    assert "jobspec" in manifest
    assert "backend" in manifest
    assert "runtime" in manifest
    assert "output" in manifest
    assert "files" in manifest

    # Check backend info
    assert manifest["backend"]["name"] == "dummy"

    # Check runtime info
    assert "python_version" in manifest["runtime"]
    assert "platform" in manifest["runtime"]

    # Check output info
    assert manifest["output"]["out_dir"] == str(tmp_path)
    assert manifest["output"]["total_files"] == 2
    assert ".png" in manifest["output"]["by_suffix_counts"]
    assert ".json" in manifest["output"]["by_suffix_counts"]


def test_build_manifest_files_sorted(tmp_path: Path):
    """Test that manifest files list is sorted."""
    cfg = JobConfig(
        job_name="test",
        out_dir=str(tmp_path),
        num_frames=1,
        dt=0.1,
    )
    backend = DummyBackend()

    # Create files in non-alphabetical order
    (tmp_path / "z.png").write_bytes(b"data")
    (tmp_path / "a.png").write_bytes(b"data")
    (tmp_path / "m.png").write_bytes(b"data")

    manifest = build_manifest(cfg, backend, "dummy", tmp_path)

    file_paths = [f["path"] for f in manifest["files"]]
    assert file_paths == sorted(file_paths)


def test_write_manifest(tmp_path: Path):
    """Test that write_manifest writes manifest.json correctly."""
    cfg = JobConfig(
        job_name="test",
        out_dir=str(tmp_path),
        num_frames=1,
        dt=0.1,
    )
    backend = DummyBackend()

    manifest = build_manifest(cfg, backend, "dummy", tmp_path)
    write_manifest(manifest, tmp_path)

    manifest_path = tmp_path / "manifest.json"
    assert manifest_path.exists()

    # Verify it's valid JSON
    with open(manifest_path, "r", encoding="utf-8") as f:
        loaded = json.load(f)

    assert loaded["schema_version"] == "manifest.v1"
    assert loaded["backend"]["name"] == "dummy"


def test_manifest_config_hash_stable():
    """Test that config_hash in manifest is stable for same config."""
    cfg1 = JobConfig(
        job_name="test",
        out_dir="outputs/test",
        num_frames=10,
        dt=0.1,
        sensors=[],
    )
    # Create config with same values but different order (via dict)
    cfg2_dict = {
        "dt": 0.1,
        "job_name": "test",
        "num_frames": 10,
        "out_dir": "outputs/test",
        "sensors": [],
    }
    cfg2 = JobConfig.model_validate(cfg2_dict)

    backend = DummyBackend()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)

        manifest1 = build_manifest(cfg1, backend, "dummy", tmp_path)
        manifest2 = build_manifest(cfg2, backend, "dummy", tmp_path)

        # Config hashes should be the same
        assert manifest1["config_hash"] == manifest2["config_hash"]


def test_manifest_config_hash_different():
    """Test that config_hash differs when config values differ."""
    cfg1 = JobConfig(
        job_name="test1",
        out_dir="outputs/test",
        num_frames=10,
        dt=0.1,
    )
    cfg2 = JobConfig(
        job_name="test2",  # Different name
        out_dir="outputs/test",
        num_frames=10,
        dt=0.1,
    )

    backend = DummyBackend()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)

        manifest1 = build_manifest(cfg1, backend, "dummy", tmp_path)
        manifest2 = build_manifest(cfg2, backend, "dummy", tmp_path)

        # Config hashes should be different
        assert manifest1["config_hash"] != manifest2["config_hash"]
