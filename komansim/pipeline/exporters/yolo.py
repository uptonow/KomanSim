"""YOLO format exporter.

Converts annotations.jsonl to YOLO txt label format for object detection.
Creates Ultralytics-compatible dataset structure with dataset.yaml.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Dict, List

import imageio.v2 as imageio


def load_annotations(annotations_path: Path) -> List[Dict[str, Any]]:
    """Load annotations from annotations.jsonl file.

    Args:
        annotations_path: Path to annotations.jsonl file

    Returns:
        List of annotation dictionaries
    """
    annotations = []
    with open(annotations_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                annotations.append(json.loads(line))
    return annotations


def bbox_xyxy_to_yolo(
    bbox_xyxy: List[float],
    image_width: int,
    image_height: int,
) -> List[float]:
    """Convert bbox from [x_min, y_min, x_max, y_max] to YOLO format [center_x, center_y, width, height] (normalized).

    Args:
        bbox_xyxy: Bounding box as [x_min, y_min, x_max, y_max] in pixels
        image_width: Image width in pixels
        image_height: Image height in pixels

    Returns:
        Bounding box as [center_x, center_y, width, height] normalized to [0, 1]
    """
    x_min, y_min, x_max, y_max = bbox_xyxy

    # Clamp to image boundaries
    x_min = max(0, min(x_min, image_width))
    y_min = max(0, min(y_min, image_height))
    x_max = max(0, min(x_max, image_width))
    y_max = max(0, min(y_max, image_height))

    # Calculate center and dimensions
    center_x = (x_min + x_max) / 2.0
    center_y = (y_min + y_max) / 2.0
    width = x_max - x_min
    height = y_max - y_min

    # Normalize to [0, 1]
    center_x_norm = center_x / image_width
    center_y_norm = center_y / image_height
    width_norm = width / image_width
    height_norm = height / image_height

    return [center_x_norm, center_y_norm, width_norm, height_norm]


def export_yolo(
    annotations_path: Path,
    out_dir: Path,
    output_dir: Path | None = None,
) -> Path:
    """Export annotations to YOLO txt label format with Ultralytics-compatible structure.

    Creates:
    - exports/yolo/labels/train/*.txt and labels/val/*.txt
    - exports/yolo/images/train/*.png and images/val/*.png
    - exports/yolo/dataset.yaml

    Args:
        annotations_path: Path to annotations.jsonl file
        out_dir: Output directory where images are stored (for reading image dimensions)
        output_dir: Optional output directory for YOLO dataset (default: exports/yolo/ in out_dir)

    Returns:
        Path to the created YOLO dataset directory (exports/yolo/)
    """

    # Load annotations
    annotations = load_annotations(annotations_path)

    # Determine output directory
    if output_dir is None:
        exports_dir = out_dir / "exports"
        exports_dir.mkdir(parents=True, exist_ok=True)
        output_dir = exports_dir / "yolo"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Create Ultralytics structure
    images_train_dir = output_dir / "images" / "train"
    images_val_dir = output_dir / "images" / "val"
    labels_train_dir = output_dir / "labels" / "train"
    labels_val_dir = output_dir / "labels" / "val"

    images_train_dir.mkdir(parents=True, exist_ok=True)
    images_val_dir.mkdir(parents=True, exist_ok=True)
    labels_train_dir.mkdir(parents=True, exist_ok=True)
    labels_val_dir.mkdir(parents=True, exist_ok=True)

    # Collect all class IDs for dataset.yaml
    class_ids = set()
    num_frames = len(annotations)

    # Split: 80% train, 20% val (deterministic based on frame_id)
    train_split = 0.8
    train_threshold = int(num_frames * train_split)

    # Process each annotation
    for ann in annotations:
        frame_id = ann.get("frame_id")
        image_path = ann.get("image_path")

        if not image_path:
            continue

        # Load image to get dimensions
        full_image_path = out_dir / image_path
        if not full_image_path.exists():
            continue

        try:
            img = imageio.imread(full_image_path)
            if len(img.shape) == 3:
                height, width = img.shape[:2]
            else:
                height, width = img.shape
        except Exception:
            # If we can't read the image, skip this frame
            continue

        # Determine train/val split
        is_train = frame_id < train_threshold
        images_dir = images_train_dir if is_train else images_val_dir
        labels_dir = labels_train_dir if is_train else labels_val_dir

        # Get frame string for filename
        frame_str = f"{frame_id:06d}"
        image_filename = f"{frame_str}.png"
        label_filename = f"{frame_str}.txt"

        # Copy image to appropriate directory
        dest_image_path = images_dir / image_filename
        if not dest_image_path.exists():
            shutil.copy2(full_image_path, dest_image_path)

        # Process objects and write label file
        objects = ann.get("objects", [])
        label_lines = []

        for obj in objects:
            class_id = obj.get("class_id")
            bbox_xyxy = obj.get("bbox_xyxy")

            if bbox_xyxy is None or class_id is None:
                continue

            class_ids.add(class_id)

            # Convert bbox to YOLO format
            bbox_yolo = bbox_xyxy_to_yolo(bbox_xyxy, width, height)

            # Format: class_id center_x center_y width height
            label_line = f"{class_id} {bbox_yolo[0]:.6f} {bbox_yolo[1]:.6f} {bbox_yolo[2]:.6f} {bbox_yolo[3]:.6f}"
            label_lines.append(label_line)

        # Write label file (even if empty, YOLO expects a file for each image)
        label_path = labels_dir / label_filename
        with open(label_path, "w", encoding="utf-8") as f:
            f.write("\n".join(label_lines))
            if label_lines:
                f.write("\n")

    # Create dataset.yaml
    class_ids_sorted = sorted(class_ids)
    class_names = [f"class_{cid}" for cid in class_ids_sorted]

    # Use absolute path for dataset root
    dataset_yaml_path = output_dir / "dataset.yaml"
    dataset_yaml_content = f"""# YOLO dataset configuration (Ultralytics format)
# Generated by KomanSim

path: {output_dir.absolute()}
train: images/train
val: images/val

# Class names
names:
"""
    for i, class_id in enumerate(class_ids_sorted):
        dataset_yaml_content += f"  {class_id}: {class_names[i]}\n"

    with open(dataset_yaml_path, "w", encoding="utf-8") as f:
        f.write(dataset_yaml_content)

    return output_dir
