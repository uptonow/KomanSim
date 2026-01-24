"""Tests for QA and preview generation."""

from __future__ import annotations

import json
import tempfile
import zipfile
from pathlib import Path

import imageio.v2 as imageio
import numpy as np

from komansim.pipeline.annotations import generate_annotations, write_annotations
from komansim.pipeline.package import create_package
from komansim.pipeline.qa import generate_qa, generate_previews


def test_generate_qa_basic_stats():
    """Test QA generation computes basic statistics."""
    with tempfile.TemporaryDirectory() as tmpdir:
        out_dir = Path(tmpdir)

        # Create directories
        (out_dir / "rgb").mkdir()
        (out_dir / "seg").mkdir()

        # Create sample images and annotations
        num_frames = 5
        seg_arrays = []

        for i in range(num_frames):
            # Create a simple RGB image
            img = np.zeros((100, 100, 3), dtype=np.uint8)
            img[20:40, 30:60] = [255, 0, 0]  # Red rectangle
            imageio.imwrite(out_dir / "rgb" / f"{i:06d}.png", img)

            # Create segmentation mask
            seg = np.zeros((100, 100), dtype=np.int32)
            seg[20:40, 30:60] = 1  # Object with instance_id=1
            np.save(out_dir / "seg" / f"{i:06d}.npy", seg)
            seg_arrays.append(seg)

        # Generate annotations
        annotations = generate_annotations(
            out_dir=out_dir,
            num_frames=num_frames,
            seg_arrays=seg_arrays,
            meta_list=None,
            min_bbox_area=1,
            validate_integrity_checks=False,
        )
        write_annotations(annotations, out_dir, validate=True)

        # Generate QA
        annotations_path = out_dir / "annotations.jsonl"
        qa_path = out_dir / "qa.json"
        qa_data = generate_qa(annotations_path, qa_path, previews_dir=None)

        # Verify QA file exists
        assert qa_path.exists()

        # Verify required keys
        assert "frames_generated" in qa_data
        assert "num_annotations_total" in qa_data
        assert "per_class_counts" in qa_data
        assert "bbox_area_stats_per_class" in qa_data

        # Verify statistics
        assert qa_data["frames_generated"] == num_frames
        assert qa_data["num_annotations_total"] == num_frames  # One object per frame
        assert len(qa_data["per_class_counts"]) > 0

        # Verify bbox stats exist for the class
        assert len(qa_data["bbox_area_stats_per_class"]) > 0
        for class_id, stats in qa_data["bbox_area_stats_per_class"].items():
            assert "min" in stats
            assert "median" in stats
            assert "max" in stats
            assert "p90" in stats


def test_generate_qa_with_previews():
    """Test QA generation includes previews list when previews_dir exists."""
    with tempfile.TemporaryDirectory() as tmpdir:
        out_dir = Path(tmpdir)

        # Create directories
        (out_dir / "rgb").mkdir()
        (out_dir / "seg").mkdir()
        (out_dir / "previews").mkdir()

        # Create sample images
        num_frames = 3
        for i in range(num_frames):
            img = np.zeros((100, 100, 3), dtype=np.uint8)
            imageio.imwrite(out_dir / "rgb" / f"{i:06d}.png", img)

        # Create preview files
        for i in range(2):
            preview_img = np.zeros((50, 50, 3), dtype=np.uint8)
            imageio.imwrite(out_dir / "previews" / f"preview_{i:03d}.jpg", preview_img)

        # Generate annotations
        seg_arrays = [np.zeros((100, 100), dtype=np.int32) for _ in range(num_frames)]
        annotations = generate_annotations(
            out_dir=out_dir,
            num_frames=num_frames,
            seg_arrays=seg_arrays,
            meta_list=None,
            min_bbox_area=1,
            validate_integrity_checks=False,
        )
        write_annotations(annotations, out_dir, validate=True)

        # Generate QA with previews
        annotations_path = out_dir / "annotations.jsonl"
        qa_path = out_dir / "qa.json"
        previews_dir = out_dir / "previews"
        qa_data = generate_qa(annotations_path, qa_path, previews_dir=previews_dir)

        # Verify previews list exists
        assert "previews" in qa_data
        assert isinstance(qa_data["previews"], list)
        assert len(qa_data["previews"]) == 2


def test_generate_previews_creates_images():
    """Test preview generation creates preview images."""
    with tempfile.TemporaryDirectory() as tmpdir:
        out_dir = Path(tmpdir)
        (out_dir / "rgb").mkdir()

        # Create sample RGB images
        num_images = 10
        for i in range(num_images):
            img = np.zeros((200, 200, 3), dtype=np.uint8)
            img[50:150, 50:150] = [255, 0, 0]  # Red square
            imageio.imwrite(out_dir / "rgb" / f"{i:06d}.png", img)

        # Generate previews (default: 8)
        previews_dir = generate_previews(out_dir, num_previews=8, max_size=512)

        # Verify previews directory exists
        assert previews_dir.exists()
        assert previews_dir.is_dir()

        # Verify preview files exist
        preview_files = list(previews_dir.glob("*.jpg"))
        assert len(preview_files) == 8  # Should create 8 previews

        # Verify previews are downscaled (should be <= 512 on long side)
        for preview_file in preview_files:
            img = imageio.imread(preview_file)
            h, w = img.shape[:2]
            assert max(h, w) <= 512


def test_generate_previews_handles_missing_rgb():
    """Test preview generation handles missing rgb directory gracefully."""
    with tempfile.TemporaryDirectory() as tmpdir:
        out_dir = Path(tmpdir)

        # Don't create rgb directory
        previews_dir = generate_previews(out_dir, num_previews=8)

        # Should return previews_dir path but not create it
        assert previews_dir == out_dir / "previews"
        assert not previews_dir.exists()


def test_qa_in_pipeline_with_dummy_backend(tmp_path: Path, monkeypatch):
    """Test that QA is generated when running a job with dummy backend."""
    # Mock home directory
    fake_home = tmp_path / "fake_home"
    fake_home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: fake_home)

    # Create a minimal config
    config_file = tmp_path / "test_config.yaml"
    import yaml

    config_data = {
        "job_name": "qa_test",
        "out_dir": str(tmp_path / "outputs" / "qa_test"),
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
    from komansim.runtime.run_job import run_job

    result = run_job(config_path_or_obj=config_file, backend="dummy", use_cache=False)

    # Verify result succeeded
    assert result.status == "succeeded"

    # Verify qa.json exists
    out_dir = tmp_path / "outputs" / "qa_test"
    qa_path = out_dir / "qa.json"
    assert qa_path.exists(), "qa.json should be generated"

    # Verify qa.json content
    with open(qa_path, "r", encoding="utf-8") as f:
        qa_data = json.load(f)

    assert "frames_generated" in qa_data
    assert "num_annotations_total" in qa_data
    assert qa_data["frames_generated"] == 3


def test_qa_included_in_package():
    """Test that qa.json is included in the packaged zip."""
    with tempfile.TemporaryDirectory() as tmpdir:
        out_dir = Path(tmpdir)

        # Create required files
        (out_dir / "rgb").mkdir()
        (out_dir / "seg").mkdir()
        (out_dir / "exports").mkdir()

        # Create manifest.json
        manifest = {
            "schema_version": "manifest.v1",
            "run_id": "test-run",
        }
        with open(out_dir / "manifest.json", "w", encoding="utf-8") as f:
            json.dump(manifest, f)

        # Create annotations.jsonl
        num_frames = 3
        seg_arrays = []
        for i in range(num_frames):
            img = np.zeros((100, 100, 3), dtype=np.uint8)
            imageio.imwrite(out_dir / "rgb" / f"{i:06d}.png", img)
            seg = np.zeros((100, 100), dtype=np.int32)
            seg[20:40, 30:60] = 1
            np.save(out_dir / "seg" / f"{i:06d}.npy", seg)
            seg_arrays.append(seg)

        annotations = generate_annotations(
            out_dir=out_dir,
            num_frames=num_frames,
            seg_arrays=seg_arrays,
            meta_list=None,
            min_bbox_area=1,
            validate_integrity_checks=False,
        )
        write_annotations(annotations, out_dir, validate=True)

        # Create exports
        (out_dir / "exports" / "yolo").mkdir()
        (out_dir / "exports" / "coco.json").write_text("{}")

        # Generate QA
        annotations_path = out_dir / "annotations.jsonl"
        qa_path = out_dir / "qa.json"
        generate_qa(annotations_path, qa_path, previews_dir=None)

        # Create package
        package_path = create_package(out_dir, format="zip")

        # Verify package exists
        assert package_path.exists()

        # Extract and verify qa.json is in package
        extract_dir = Path(tmpdir) / "extracted"
        extract_dir.mkdir()

        with zipfile.ZipFile(package_path, "r") as zf:
            zf.extractall(extract_dir)

            # Check qa.json exists in package
            extracted_qa = extract_dir / "qa.json"
            assert extracted_qa.exists(), "qa.json should be in package"

            # Verify content
            with open(extracted_qa, "r", encoding="utf-8") as f:
                qa_data = json.load(f)
            assert "frames_generated" in qa_data
            assert qa_data["frames_generated"] == num_frames
