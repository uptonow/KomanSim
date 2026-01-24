"""Tests for exporters and packaging."""

from __future__ import annotations

import json
import tempfile
import zipfile
from pathlib import Path

import imageio.v2 as imageio
import numpy as np
import pytest

from komansim.pipeline.annotations import generate_annotations, write_annotations
from komansim.pipeline.exporters.coco import export_coco
from komansim.pipeline.exporters.yolo import export_yolo
from komansim.pipeline.package import create_package


def test_coco_export_structure():
    """Test COCO export contains images/annotations/categories keys."""
    with tempfile.TemporaryDirectory() as tmpdir:
        out_dir = Path(tmpdir)

        # Create directories and files
        (out_dir / "rgb").mkdir()
        (out_dir / "seg").mkdir()

        # Create sample images and annotations
        num_frames = 3
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

        # Export to COCO
        annotations_path = out_dir / "annotations.jsonl"
        coco_path = export_coco(annotations_path, out_dir)

        # Verify COCO JSON structure
        assert coco_path.exists()

        with open(coco_path, "r", encoding="utf-8") as f:
            coco_data = json.load(f)

        # Check required keys
        assert "images" in coco_data
        assert "annotations" in coco_data
        assert "categories" in coco_data

        # Check images
        assert len(coco_data["images"]) == num_frames
        for img in coco_data["images"]:
            assert "id" in img
            assert "file_name" in img
            assert "width" in img
            assert "height" in img

        # Check annotations
        assert len(coco_data["annotations"]) == num_frames  # One annotation per frame
        for ann in coco_data["annotations"]:
            assert "id" in ann
            assert "image_id" in ann
            assert "category_id" in ann
            assert "bbox" in ann
            assert "area" in ann
            assert "iscrowd" in ann
            assert len(ann["bbox"]) == 4  # [x, y, width, height]

        # Check categories
        assert len(coco_data["categories"]) > 0
        for cat in coco_data["categories"]:
            assert "id" in cat
            assert "name" in cat
            assert "supercategory" in cat


def test_coco_bbox_format():
    """Test COCO bbox format is [x, y, width, height]."""
    with tempfile.TemporaryDirectory() as tmpdir:
        out_dir = Path(tmpdir)

        # Create directories and files
        (out_dir / "rgb").mkdir()
        (out_dir / "seg").mkdir()

        # Create a single image with known bbox
        img = np.zeros((200, 300, 3), dtype=np.uint8)
        imageio.imwrite(out_dir / "rgb" / "000000.png", img)

        # Create segmentation mask with object at [50, 30, 150, 80]
        seg = np.zeros((200, 300), dtype=np.int32)
        seg[30:80, 50:150] = 1
        np.save(out_dir / "seg" / "000000.npy", seg)

        # Generate annotations
        annotations = generate_annotations(
            out_dir=out_dir,
            num_frames=1,
            seg_arrays=[seg],
            meta_list=None,
            min_bbox_area=1,
            validate_integrity_checks=False,
        )
        write_annotations(annotations, out_dir, validate=True)

        # Export to COCO
        annotations_path = out_dir / "annotations.jsonl"
        coco_path = export_coco(annotations_path, out_dir)

        # Check bbox format
        with open(coco_path, "r", encoding="utf-8") as f:
            coco_data = json.load(f)

        assert len(coco_data["annotations"]) == 1
        bbox = coco_data["annotations"][0]["bbox"]

        # COCO format: [x, y, width, height]
        assert len(bbox) == 4
        assert bbox[0] == 50.0  # x
        assert bbox[1] == 30.0  # y
        assert bbox[2] == 100.0  # width (150 - 50)
        assert bbox[3] == 50.0  # height (80 - 30)


def test_yolo_export_labels_exist():
    """Test YOLO labels exist for sample frames."""
    with tempfile.TemporaryDirectory() as tmpdir:
        out_dir = Path(tmpdir)

        # Create directories and files
        (out_dir / "rgb").mkdir()
        (out_dir / "seg").mkdir()

        # Create sample images and annotations
        num_frames = 3
        seg_arrays = []

        for i in range(num_frames):
            # Create a simple RGB image
            img = np.zeros((100, 100, 3), dtype=np.uint8)
            img[20:40, 30:60] = [255, 0, 0]
            imageio.imwrite(out_dir / "rgb" / f"{i:06d}.png", img)

            # Create segmentation mask
            seg = np.zeros((100, 100), dtype=np.int32)
            seg[20:40, 30:60] = i + 1  # Different instance_id per frame
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

        # Export to YOLO
        annotations_path = out_dir / "annotations.jsonl"
        yolo_dir = export_yolo(annotations_path, out_dir)

        # Verify YOLO labels exist (Ultralytics structure)
        assert yolo_dir.exists()
        assert yolo_dir.is_dir()

        # Check labels are in train/val directories
        labels_train_dir = yolo_dir / "labels" / "train"
        labels_val_dir = yolo_dir / "labels" / "val"

        all_labels = list(labels_train_dir.glob("*.txt")) + list(labels_val_dir.glob("*.txt"))
        assert len(all_labels) == num_frames, (
            f"Should have {num_frames} label files, got {len(all_labels)}"
        )

        for i in range(num_frames):
            frame_str = f"{i:06d}"
            # Label could be in train or val
            label_path_train = labels_train_dir / f"{frame_str}.txt"
            label_path_val = labels_val_dir / f"{frame_str}.txt"
            assert label_path_train.exists() or label_path_val.exists(), (
                f"YOLO label file for frame {frame_str} should exist"
            )

            label_path = label_path_train if label_path_train.exists() else label_path_val

            # Check label content
            content = label_path.read_text().strip()
            if content:
                lines = content.split("\n")
                assert len(lines) == 1  # One object per frame

                # Check YOLO format: class_id center_x center_y width height
                parts = lines[0].split()
                assert len(parts) == 5
                assert int(parts[0]) == i + 1  # class_id matches instance_id

                # Check normalized coordinates are in [0, 1]
                center_x = float(parts[1])
                center_y = float(parts[2])
                width = float(parts[3])
                height = float(parts[4])

                assert 0.0 <= center_x <= 1.0
                assert 0.0 <= center_y <= 1.0
                assert 0.0 <= width <= 1.0
                assert 0.0 <= height <= 1.0


def test_yolo_bbox_normalized():
    """Test YOLO bbox coordinates are normalized."""
    with tempfile.TemporaryDirectory() as tmpdir:
        out_dir = Path(tmpdir)

        # Create directories and files
        (out_dir / "rgb").mkdir()
        (out_dir / "seg").mkdir()

        # Create image with known dimensions
        img = np.zeros((200, 300, 3), dtype=np.uint8)
        imageio.imwrite(out_dir / "rgb" / "000000.png", img)

        # Create segmentation mask with object at [50, 30, 150, 80]
        seg = np.zeros((200, 300), dtype=np.int32)
        seg[30:80, 50:150] = 1
        np.save(out_dir / "seg" / "000000.npy", seg)

        # Generate annotations
        annotations = generate_annotations(
            out_dir=out_dir,
            num_frames=1,
            seg_arrays=[seg],
            meta_list=None,
            min_bbox_area=1,
            validate_integrity_checks=False,
        )
        write_annotations(annotations, out_dir, validate=True)

        # Export to YOLO
        annotations_path = out_dir / "annotations.jsonl"
        yolo_dir = export_yolo(annotations_path, out_dir)

        # Check label file (could be in train or val)
        label_path_train = yolo_dir / "labels" / "train" / "000000.txt"
        label_path_val = yolo_dir / "labels" / "val" / "000000.txt"
        assert label_path_train.exists() or label_path_val.exists(), (
            "Label file should exist in train or val"
        )
        label_path = label_path_train if label_path_train.exists() else label_path_val

        content = label_path.read_text().strip()
        parts = content.split()

        # Image: 300x200, bbox: [50, 30, 150, 80]
        # Center: (100, 55), Size: (100, 50)
        # Normalized: center_x=100/300=0.333..., center_y=55/200=0.275, width=100/300=0.333..., height=50/200=0.25
        center_x = float(parts[1])
        center_y = float(parts[2])
        width = float(parts[3])
        height = float(parts[4])

        assert abs(center_x - 100.0 / 300.0) < 0.001
        assert abs(center_y - 55.0 / 200.0) < 0.001
        assert abs(width - 100.0 / 300.0) < 0.001
        assert abs(height - 50.0 / 200.0) < 0.001


def test_yolo_ultralytics_structure():
    """Test YOLO export creates Ultralytics-compatible structure (dataset.yaml, images/train/val, labels/train/val)."""
    import yaml

    with tempfile.TemporaryDirectory() as tmpdir:
        out_dir = Path(tmpdir)

        # Create directories and files
        (out_dir / "rgb").mkdir()
        (out_dir / "seg").mkdir()

        # Create sample images and annotations (10 frames for train/val split)
        num_frames = 10
        seg_arrays = []

        for i in range(num_frames):
            # Create a simple RGB image
            img = np.zeros((100, 100, 3), dtype=np.uint8)
            img[20:40, 30:60] = [255, 0, 0]
            imageio.imwrite(out_dir / "rgb" / f"{i:06d}.png", img)

            # Create segmentation mask
            seg = np.zeros((100, 100), dtype=np.int32)
            seg[20:40, 30:60] = 1  # class_id = 1
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

        # Export to YOLO
        annotations_path = out_dir / "annotations.jsonl"
        yolo_dir = export_yolo(annotations_path, out_dir)

        # Verify Ultralytics structure exists
        assert yolo_dir.exists()
        assert yolo_dir.is_dir()

        # Check dataset.yaml exists
        dataset_yaml_path = yolo_dir / "dataset.yaml"
        assert dataset_yaml_path.exists(), "dataset.yaml should exist"

        # Load and verify dataset.yaml structure
        with open(dataset_yaml_path, "r", encoding="utf-8") as f:
            dataset_yaml = yaml.safe_load(f)

        assert "path" in dataset_yaml
        assert "train" in dataset_yaml
        assert "val" in dataset_yaml
        assert dataset_yaml["train"] == "images/train"
        assert dataset_yaml["val"] == "images/val"
        assert "names" in dataset_yaml

        # Check directories exist
        images_train_dir = yolo_dir / "images" / "train"
        images_val_dir = yolo_dir / "images" / "val"
        labels_train_dir = yolo_dir / "labels" / "train"
        labels_val_dir = yolo_dir / "labels" / "val"

        assert images_train_dir.exists() and images_train_dir.is_dir()
        assert images_val_dir.exists() and images_val_dir.is_dir()
        assert labels_train_dir.exists() and labels_train_dir.is_dir()
        assert labels_val_dir.exists() and labels_val_dir.is_dir()

        # Check that images and labels exist in train/val
        train_images = list(images_train_dir.glob("*.png"))
        val_images = list(images_val_dir.glob("*.png"))
        train_labels = list(labels_train_dir.glob("*.txt"))
        val_labels = list(labels_val_dir.glob("*.txt"))

        assert len(train_images) > 0, "Should have training images"
        assert len(val_images) > 0, "Should have validation images"
        assert len(train_labels) > 0, "Should have training labels"
        assert len(val_labels) > 0, "Should have validation labels"

        # Verify matching filenames between images and labels
        train_image_names = {img.stem for img in train_images}
        train_label_names = {label.stem for label in train_labels}
        assert train_image_names == train_label_names, (
            "Training image and label filenames should match"
        )

        val_image_names = {img.stem for img in val_images}
        val_label_names = {label.stem for label in val_labels}
        assert val_image_names == val_label_names, (
            "Validation image and label filenames should match"
        )

        # Verify at least one label file has parseable content within [0,1]
        sample_label_path = train_labels[0]
        content = sample_label_path.read_text().strip()
        if content:  # If label has content
            parts = content.split()
            assert len(parts) >= 5, "Label should have at least 5 values (class_id, x, y, w, h)"
            int(parts[0])  # class_id (verify it's parseable)
            x_center = float(parts[1])
            y_center = float(parts[2])
            width = float(parts[3])
            height = float(parts[4])

            # Verify normalized coordinates are in [0, 1]
            assert 0.0 <= x_center <= 1.0, f"x_center should be in [0,1], got {x_center}"
            assert 0.0 <= y_center <= 1.0, f"y_center should be in [0,1], got {y_center}"
            assert 0.0 <= width <= 1.0, f"width should be in [0,1], got {width}"
            assert 0.0 <= height <= 1.0, f"height should be in [0,1], got {height}"


def test_package_contains_expected_files():
    """Test package contains expected files."""
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
        annotations = [
            {"frame_id": 0, "image_path": "rgb/000000.png", "objects": []},
        ]
        write_annotations(annotations, out_dir, validate=False)

        # Create exports
        (out_dir / "exports" / "yolo").mkdir()
        (out_dir / "exports" / "yolo" / "000000.txt").write_text("")
        (out_dir / "exports" / "coco.json").write_text("{}")

        # Create previews (optional)
        (out_dir / "previews").mkdir()
        (out_dir / "previews" / "preview.png").write_bytes(b"fake image")

        # Create package
        package_path = create_package(out_dir, format="zip")

        # Verify package exists
        assert package_path.exists()
        assert package_path.suffix == ".zip"

        # Extract and verify contents
        extract_dir = Path(tmpdir) / "extracted"
        extract_dir.mkdir()

        with zipfile.ZipFile(package_path, "r") as zf:
            zf.extractall(extract_dir)

        # Check required files exist
        assert (extract_dir / "manifest.json").exists()
        assert (extract_dir / "annotations.jsonl").exists()
        assert (extract_dir / "exports" / "coco.json").exists()
        assert (extract_dir / "exports" / "yolo" / "000000.txt").exists()
        assert (extract_dir / "previews" / "preview.png").exists()


def test_package_without_previews():
    """Test package works without previews directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        out_dir = Path(tmpdir)

        # Create required files
        (out_dir / "rgb").mkdir()
        (out_dir / "exports").mkdir()

        # Create manifest.json
        manifest = {"schema_version": "manifest.v1", "run_id": "test-run"}
        with open(out_dir / "manifest.json", "w", encoding="utf-8") as f:
            json.dump(manifest, f)

        # Create annotations.jsonl
        annotations = [{"frame_id": 0, "image_path": "rgb/000000.png", "objects": []}]
        write_annotations(annotations, out_dir, validate=False)

        # Create exports
        (out_dir / "exports" / "yolo").mkdir()
        (out_dir / "exports" / "coco.json").write_text("{}")

        # Create package (previews don't exist, should still work)
        package_path = create_package(out_dir, format="zip", include_previews=True)

        # Verify package exists
        assert package_path.exists()

        # Extract and verify contents
        extract_dir = Path(tmpdir) / "extracted"
        extract_dir.mkdir()

        with zipfile.ZipFile(package_path, "r") as zf:
            zf.extractall(extract_dir)

        # Check required files exist
        assert (extract_dir / "manifest.json").exists()
        assert (extract_dir / "annotations.jsonl").exists()
        assert (extract_dir / "exports" / "coco.json").exists()

        # Previews should not be in package if directory doesn't exist
        assert not (extract_dir / "previews").exists()


def test_package_tar_format():
    """Test package works with tar format."""
    with tempfile.TemporaryDirectory() as tmpdir:
        out_dir = Path(tmpdir)

        # Create required files
        (out_dir / "rgb").mkdir()
        (out_dir / "exports").mkdir()

        # Create manifest.json
        manifest = {"schema_version": "manifest.v1", "run_id": "test-run"}
        with open(out_dir / "manifest.json", "w", encoding="utf-8") as f:
            json.dump(manifest, f)

        # Create annotations.jsonl
        annotations = [{"frame_id": 0, "image_path": "rgb/000000.png", "objects": []}]
        write_annotations(annotations, out_dir, validate=False)

        # Create exports
        (out_dir / "exports" / "coco.json").write_text("{}")

        # Create package with tar format
        package_path = create_package(out_dir, format="tar")

        # Verify package exists
        assert package_path.exists()
        assert package_path.suffix == ".tar" or package_path.suffixes == [".tar", ".gz"]


def test_package_missing_required_files():
    """Test package raises error when required files are missing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        out_dir = Path(tmpdir)

        # Missing manifest.json
        with pytest.raises(FileNotFoundError, match="manifest.json"):
            create_package(out_dir, format="zip")

        # Create manifest but missing annotations
        (out_dir / "manifest.json").write_text("{}")
        with pytest.raises(FileNotFoundError, match="annotations.jsonl"):
            create_package(out_dir, format="zip")


def test_package_contains_rgb_and_coco_file_names():
    """Test package contains rgb/ directory and COCO file_name entries exist in zip."""
    with tempfile.TemporaryDirectory() as tmpdir:
        out_dir = Path(tmpdir)

        # Create required files
        (out_dir / "rgb").mkdir()
        (out_dir / "seg").mkdir()
        (out_dir / "exports").mkdir()

        # Create sample images
        num_frames = 3
        for i in range(num_frames):
            img = np.zeros((100, 100, 3), dtype=np.uint8)
            imageio.imwrite(out_dir / "rgb" / f"{i:06d}.png", img)

            seg = np.zeros((100, 100), dtype=np.int32)
            seg[20:40, 30:60] = 1
            np.save(out_dir / "seg" / f"{i:06d}.npy", seg)

        # Create manifest.json
        manifest = {"schema_version": "manifest.v1", "run_id": "test-run"}
        with open(out_dir / "manifest.json", "w", encoding="utf-8") as f:
            json.dump(manifest, f)

        # Generate annotations and export COCO
        seg_arrays = [np.load(out_dir / "seg" / f"{i:06d}.npy") for i in range(num_frames)]
        annotations = generate_annotations(
            out_dir=out_dir,
            num_frames=num_frames,
            seg_arrays=seg_arrays,
            meta_list=None,
            min_bbox_area=1,
            validate_integrity_checks=False,
        )
        write_annotations(annotations, out_dir, validate=True)

        # Export to COCO
        annotations_path = out_dir / "annotations.jsonl"
        export_coco(annotations_path, out_dir)

        # Create package
        package_path = create_package(out_dir, format="zip")

        # Extract and verify contents
        extract_dir = Path(tmpdir) / "extracted"
        extract_dir.mkdir()

        with zipfile.ZipFile(package_path, "r") as zf:
            zf.extractall(extract_dir)

            # Check rgb/ directory exists in zip
            rgb_files_in_zip = [name for name in zf.namelist() if name.startswith("rgb/")]
            assert len(rgb_files_in_zip) > 0, "Package should contain rgb/ files"
            assert any(name == "rgb/000000.png" for name in rgb_files_in_zip)

        # Load COCO JSON from extracted package
        coco_path = extract_dir / "exports" / "coco.json"
        assert coco_path.exists(), "COCO JSON should exist in package"

        with open(coco_path, "r", encoding="utf-8") as f:
            coco_data = json.load(f)

        # Verify COCO file_name entries exist and point to files in zip
        assert "images" in coco_data
        assert len(coco_data["images"]) == num_frames

        for img_entry in coco_data["images"]:
            file_name = img_entry["file_name"]
            assert file_name.startswith("rgb/"), (
                f"COCO file_name should start with 'rgb/', got {file_name}"
            )
            # Verify the file exists in the extracted package
            extracted_file = extract_dir / file_name
            assert extracted_file.exists(), (
                f"File {file_name} from COCO should exist in extracted package"
            )
