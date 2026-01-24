"""Tests for annotations generation."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import numpy as np
import pytest

from komansim.pipeline.annotations import (
    build_frame_annotation,
    generate_annotations,
    write_annotations,
)


def test_build_frame_annotation_no_seg():
    """Test build_frame_annotation without segmentation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        out_dir = Path(tmpdir)

        # Create a dummy RGB file
        (out_dir / "rgb").mkdir()
        (out_dir / "rgb" / "000000.png").touch()

        ann = build_frame_annotation(
            frame_id=0,
            out_dir=out_dir,
            seg=None,
            meta=None,
        )

        assert ann["frame_id"] == 0
        assert ann["image_path"] == "rgb/000000.png"
        assert ann.get("seg_path") is None
        assert ann["objects"] == []


def test_build_frame_annotation_with_seg():
    """Test build_frame_annotation with segmentation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        out_dir = Path(tmpdir)

        # Create directories and files
        (out_dir / "rgb").mkdir()
        (out_dir / "rgb" / "000000.png").touch()
        (out_dir / "seg").mkdir()
        (out_dir / "seg" / "000000.npy").touch()

        # Create a simple seg mask with one object
        seg = np.zeros((100, 100), dtype=np.int32)
        seg[20:40, 30:60] = 1

        ann = build_frame_annotation(
            frame_id=0,
            out_dir=out_dir,
            seg=seg,
            meta=None,
        )

        assert ann["frame_id"] == 0
        assert ann["image_path"] == "rgb/000000.png"
        assert ann["seg_path"] == "seg/000000.npy"
        assert len(ann["objects"]) == 1

        obj = ann["objects"][0]
        assert obj["instance_id"] == 1
        assert obj["class_id"] == 1
        assert obj["bbox_xyxy"] == [30, 20, 60, 40]
        assert "mask_ref" in obj
        assert obj["mask_ref"]["path"] == "seg/000000.npy"
        assert obj["mask_ref"]["instance_id"] == 1


def test_build_frame_annotation_with_camera_meta():
    """Test build_frame_annotation with camera metadata."""
    with tempfile.TemporaryDirectory() as tmpdir:
        out_dir = Path(tmpdir)
        (out_dir / "rgb").mkdir()
        (out_dir / "rgb" / "000000.png").touch()

        meta = {
            "intrinsics": {"fx": 500.0, "fy": 500.0, "cx": 320.0, "cy": 240.0},
            "extrinsics": {"position": [0, 0, 0], "rotation": [0, 0, 0, 1]},
        }

        ann = build_frame_annotation(
            frame_id=0,
            out_dir=out_dir,
            seg=None,
            meta=meta,
        )

        assert "camera" in ann
        assert ann["camera"]["intrinsics"] == meta["intrinsics"]
        assert ann["camera"]["extrinsics"] == meta["extrinsics"]


def test_build_frame_annotation_min_bbox_area():
    """Test build_frame_annotation filters by min_bbox_area."""
    with tempfile.TemporaryDirectory() as tmpdir:
        out_dir = Path(tmpdir)
        (out_dir / "rgb").mkdir()
        (out_dir / "rgb" / "000000.png").touch()
        (out_dir / "seg").mkdir()
        (out_dir / "seg" / "000000.npy").touch()

        seg = np.zeros((100, 100), dtype=np.int32)
        seg[20:40, 30:60] = 1  # Large object
        seg[50:52, 50:52] = 2  # Small object (2x2 = 4 pixels)

        # With min_bbox_area=10, small object should be filtered
        ann = build_frame_annotation(
            frame_id=0,
            out_dir=out_dir,
            seg=seg,
            meta=None,
            min_bbox_area=10,
        )

        assert len(ann["objects"]) == 1
        assert ann["objects"][0]["instance_id"] == 1


def test_write_annotations():
    """Test write_annotations writes valid JSONL file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        out_dir = Path(tmpdir)

        annotations = [
            {
                "frame_id": 0,
                "image_path": "rgb/000000.png",
                "objects": [],
            },
            {
                "frame_id": 1,
                "image_path": "rgb/000001.png",
                "seg_path": "seg/000001.npy",
                "objects": [
                    {
                        "instance_id": 1,
                        "class_id": 1,
                        "bbox_xyxy": [10, 10, 50, 50],
                    },
                ],
            },
        ]

        write_annotations(annotations, out_dir, validate=True)

        # Check file exists
        annotations_path = out_dir / "annotations.jsonl"
        assert annotations_path.exists()

        # Read and verify content
        lines = annotations_path.read_text().strip().split("\n")
        assert len(lines) == 2

        for i, line in enumerate(lines):
            ann = json.loads(line)
            assert ann["frame_id"] == i


def test_write_annotations_validation_error():
    """Test write_annotations raises error on invalid annotations."""
    with tempfile.TemporaryDirectory() as tmpdir:
        out_dir = Path(tmpdir)

        # Invalid annotation: objects but no seg_path
        annotations = [
            {
                "frame_id": 0,
                "image_path": "rgb/000000.png",
                "objects": [
                    {
                        "instance_id": 1,
                        "class_id": 1,
                        "bbox_xyxy": [10, 10, 50, 50],
                    },
                ],
            },
        ]

        with pytest.raises(ValueError, match="validation failed"):
            write_annotations(annotations, out_dir, validate=True)


def test_generate_annotations():
    """Test generate_annotations creates annotations for all frames."""
    with tempfile.TemporaryDirectory() as tmpdir:
        out_dir = Path(tmpdir)

        # Create directories
        (out_dir / "rgb").mkdir()
        (out_dir / "seg").mkdir()

        # Create dummy files
        for i in range(3):
            (out_dir / "rgb" / f"{i:06d}.png").touch()
            (out_dir / "seg" / f"{i:06d}.npy").touch()

        # Create seg arrays
        seg_arrays = []
        for i in range(3):
            seg = np.zeros((100, 100), dtype=np.int32)
            seg[20 + i * 10 : 30 + i * 10, 20 + i * 10 : 30 + i * 10] = i + 1
            seg_arrays.append(seg)

        annotations = generate_annotations(
            out_dir=out_dir,
            num_frames=3,
            seg_arrays=seg_arrays,
            meta_list=None,
            min_bbox_area=1,
            validate_integrity_checks=True,
        )

        assert len(annotations) == 3
        for i, ann in enumerate(annotations):
            assert ann["frame_id"] == i
            assert len(ann["objects"]) == 1
            assert ann["objects"][0]["instance_id"] == i + 1


def test_generate_annotations_missing_files():
    """Test generate_annotations handles missing files gracefully."""
    with tempfile.TemporaryDirectory() as tmpdir:
        out_dir = Path(tmpdir)

        # Don't create any files
        annotations = generate_annotations(
            out_dir=out_dir,
            num_frames=2,
            seg_arrays=None,
            meta_list=None,
            min_bbox_area=1,
            validate_integrity_checks=False,
        )

        assert len(annotations) == 2
        for i, ann in enumerate(annotations):
            assert ann["frame_id"] == i
            assert ann.get("image_path") is None
            assert ann.get("seg_path") is None
            assert ann["objects"] == []
