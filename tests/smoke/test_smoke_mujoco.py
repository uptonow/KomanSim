"""Smoke test for MuJoCo backend with real rendering.

This test verifies that the MuJoCo backend produces real RGB, depth, and segmentation
outputs that can be used by the pipeline to generate annotations, COCO, and YOLO exports.

The test is skipped unless SIMDATA_REAL_BACKEND=1 is set to avoid requiring
MuJoCo and EGL/OSMesa in CI environments.
"""

import os
import json
from pathlib import Path

import pytest
import yaml

from komansim.runtime.run_job import run_job


def _should_run_real_backend_test() -> bool:
    """Check if real backend tests should run."""
    return os.environ.get("SIMDATA_REAL_BACKEND", "0") == "1"


def _mujoco_available() -> bool:
    """Check if MuJoCo package is available."""
    try:
        import mujoco  # noqa: F401

        return True
    except ImportError:
        return False


@pytest.mark.skipif(
    not _should_run_real_backend_test(),
    reason="Set SIMDATA_REAL_BACKEND=1 to run real backend tests",
)
@pytest.mark.skipif(
    not _mujoco_available(), reason="MuJoCo package not available. Install with: pip install mujoco"
)
def test_smoke_mujoco_backend(tmp_path: Path):
    """Smoke test for MuJoCo backend with real rendering.

    This test:
    1. Runs a minimal job with MuJoCo backend
    2. Verifies outputs exist (manifest, annotations, COCO, YOLO, package)
    3. Verifies at least one frame contains objects
    4. Verifies segmentation has >1 unique value (background + at least one object)
    """
    # Load smoke test config
    config_path = Path(__file__).parent.parent.parent / "examples" / "configs" / "mujoco_smoke.yaml"
    if not config_path.exists():
        pytest.skip(f"Smoke test config not found: {config_path}")

    # Override output directory to use tmp_path
    with open(config_path, "r") as f:
        config_data = yaml.safe_load(f)

    config_data["out_dir"] = str(tmp_path / "smoke_mujoco")

    # Write modified config to tmp_path
    test_config_path = tmp_path / "test_config.yaml"
    with open(test_config_path, "w") as f:
        yaml.safe_dump(config_data, f)

    # Run the job
    run_job(config_path_or_obj=test_config_path, backend="mujoco")

    out_dir = tmp_path / "smoke_mujoco"

    # Verify output directory exists
    assert out_dir.exists(), "Output directory should exist"

    # Verify manifest exists
    manifest_path = out_dir / "manifest.json"
    assert manifest_path.exists(), "manifest.json should exist"

    manifest = json.loads(manifest_path.read_text())
    assert manifest["jobspec"]["job_name"] == "smoke_mujoco"
    assert manifest["backend"]["name"] == "mujoco"
    assert "version" in manifest["backend"]

    # Verify annotations.jsonl exists
    annotations_path = out_dir / "annotations.jsonl"
    assert annotations_path.exists(), "annotations.jsonl should exist"

    # Read annotations
    annotations = []
    with open(annotations_path, "r") as f:
        for line in f:
            if line.strip():
                annotations.append(json.loads(line))

    assert len(annotations) == config_data["num_frames"], (
        f"Expected {config_data['num_frames']} annotations, got {len(annotations)}"
    )

    # Verify COCO export exists
    coco_path = out_dir / "exports" / "coco.json"
    assert coco_path.exists(), "COCO export should exist"

    coco_data = json.loads(coco_path.read_text())
    assert "images" in coco_data
    assert "annotations" in coco_data
    assert "categories" in coco_data

    # Verify YOLO export exists
    yolo_dir = out_dir / "exports" / "yolo"
    assert yolo_dir.exists(), "YOLO export directory should exist"

    # Verify package exists (package is created at {out_dir}.zip, not inside out_dir)
    package_path = tmp_path / "smoke_mujoco.zip"
    assert package_path.exists(), f"Package zip file should exist at {package_path}"

    # Verify RGB frames exist
    rgb_dir = out_dir / "rgb"
    assert rgb_dir.exists(), "RGB directory should exist"

    rgb_files = list(rgb_dir.glob("*.png"))
    assert len(rgb_files) == config_data["num_frames"], (
        f"Expected {config_data['num_frames']} RGB files, got {len(rgb_files)}"
    )

    # Verify segmentation frames exist
    seg_dir = out_dir / "seg"
    assert seg_dir.exists(), "Segmentation directory should exist"

    seg_files = list(seg_dir.glob("*.npy"))
    assert len(seg_files) > 0, "At least one segmentation file should exist"

    # Verify at least one frame contains objects (segmentation has >1 unique value)
    import numpy as np

    frames_with_objects = 0
    for seg_file in seg_files:
        seg = np.load(seg_file)
        unique_values = np.unique(seg)
        # Should have background (0) and at least one object (>=1)
        if len(unique_values) > 1:
            frames_with_objects += 1
            # Verify at least one non-zero value exists
            assert np.any(seg > 0), (
                f"Segmentation {seg_file} should have at least one non-zero pixel"
            )

    assert frames_with_objects > 0, (
        "At least one frame should contain objects (segmentation should have >1 unique value)"
    )

    # Verify annotations reference objects
    frames_with_annotations = sum(1 for ann in annotations if len(ann.get("objects", [])) > 0)
    assert frames_with_annotations > 0, "At least one annotation should contain objects"

    # Verify segmentation encoding in metadata
    if seg_files:
        meta_path = out_dir / "meta" / "000000.json"
        if meta_path.exists():
            meta = json.loads(meta_path.read_text())
            # Check if seg_encoding is in frame metadata or backend metadata
            assert "seg_encoding" in meta or "seg_encoding" in manifest.get("backend", {}), (
                "Segmentation encoding should be documented in metadata"
            )


@pytest.mark.skipif(
    not _should_run_real_backend_test(),
    reason="Set SIMDATA_REAL_BACKEND=1 to run real backend tests",
)
@pytest.mark.skipif(not _mujoco_available(), reason="MuJoCo package not available")
def test_smoke_mujoco_segmentation_values(tmp_path: Path):
    """Test that segmentation masks have correct value ranges.

    Segmentation should be int32 with 0=background and 1..K for instances.
    """
    import numpy as np

    # Load smoke test config
    config_path = Path(__file__).parent.parent.parent / "examples" / "configs" / "mujoco_smoke.yaml"
    if not config_path.exists():
        pytest.skip(f"Smoke test config not found: {config_path}")

    with open(config_path, "r") as f:
        config_data = yaml.safe_load(f)

    config_data["out_dir"] = str(tmp_path / "smoke_mujoco_seg")
    config_data["num_frames"] = 5  # Fewer frames for faster test

    test_config_path = tmp_path / "test_config.yaml"
    with open(test_config_path, "w") as f:
        yaml.safe_dump(config_data, f)

    # Run the job
    run_job(config_path_or_obj=test_config_path, backend="mujoco")

    out_dir = tmp_path / "smoke_mujoco_seg"
    seg_dir = out_dir / "seg"

    if not seg_dir.exists():
        pytest.skip("Segmentation directory not created")

    seg_files = list(seg_dir.glob("*.npy"))
    assert len(seg_files) > 0, "At least one segmentation file should exist"

    # Check segmentation properties
    for seg_file in seg_files:
        seg = np.load(seg_file)

        # Should be 2D array
        assert seg.ndim == 2, f"Segmentation should be 2D, got shape {seg.shape}"

        # Should be int32
        assert seg.dtype == np.int32, f"Segmentation should be int32, got {seg.dtype}"

        # Should have non-negative values
        assert np.all(seg >= 0), (
            f"Segmentation should have non-negative values, got min={seg.min()}"
        )

        # Background (0) should be present
        assert 0 in np.unique(seg), "Background (0) should be present in segmentation"
