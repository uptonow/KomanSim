"""COCO format exporter.

Converts annotations.jsonl to COCO JSON format for object detection/segmentation.
"""

from __future__ import annotations

import json
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


def bbox_xyxy_to_coco(bbox_xyxy: List[float], image_width: int, image_height: int) -> List[float]:
    """Convert bbox from [x_min, y_min, x_max, y_max] to COCO format [x, y, width, height].

    Args:
        bbox_xyxy: Bounding box as [x_min, y_min, x_max, y_max]
        image_width: Image width in pixels
        image_height: Image height in pixels

    Returns:
        Bounding box as [x, y, width, height] in COCO format
    """
    x_min, y_min, x_max, y_max = bbox_xyxy

    # Clamp to image boundaries
    x_min = max(0, min(x_min, image_width))
    y_min = max(0, min(y_min, image_height))
    x_max = max(0, min(x_max, image_width))
    y_max = max(0, min(y_max, image_height))

    x = x_min
    y = y_min
    width = x_max - x_min
    height = y_max - y_min

    return [x, y, width, height]


def build_coco_dataset(
    annotations: List[Dict[str, Any]],
    out_dir: Path,
) -> Dict[str, Any]:
    """Build COCO format dataset from annotations.

    Args:
        annotations: List of frame annotation dictionaries
        out_dir: Output directory where images are stored

    Returns:
        COCO format dictionary with keys: images, annotations, categories
    """
    coco_images: List[Dict[str, Any]] = []
    coco_annotations: List[Dict[str, Any]] = []
    categories_map: Dict[int, Dict[str, Any]] = {}

    image_id_counter = 1
    annotation_id_counter = 1

    for ann in annotations:
        _frame_id = ann.get("frame_id")  # Not used in COCO export
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

        # Add image entry
        coco_image = {
            "id": image_id_counter,
            "file_name": image_path,
            "width": int(width),
            "height": int(height),
        }
        coco_images.append(coco_image)

        # Process objects
        objects = ann.get("objects", [])
        for obj in objects:
            _instance_id = obj.get("instance_id")  # Not used in COCO export
            class_id = obj.get("class_id")
            bbox_xyxy = obj.get("bbox_xyxy")

            if bbox_xyxy is None:
                continue

            # Convert bbox to COCO format
            bbox_coco = bbox_xyxy_to_coco(bbox_xyxy, width, height)

            # Calculate area
            area = bbox_coco[2] * bbox_coco[3]  # width * height

            # Add annotation entry
            coco_annotation = {
                "id": annotation_id_counter,
                "image_id": image_id_counter,
                "category_id": class_id,
                "bbox": bbox_coco,
                "area": float(area),
                "iscrowd": 0,
            }
            coco_annotations.append(coco_annotation)

            # Track category
            if class_id not in categories_map:
                categories_map[class_id] = {
                    "id": class_id,
                    "name": f"class_{class_id}",
                    "supercategory": "object",
                }

            annotation_id_counter += 1

        image_id_counter += 1

    # Convert categories map to list
    categories = list(categories_map.values())
    categories.sort(key=lambda x: x["id"])

    coco_dataset = {
        "images": coco_images,
        "annotations": coco_annotations,
        "categories": categories,
    }

    return coco_dataset


def export_coco(
    annotations_path: Path,
    out_dir: Path,
    output_path: Path | None = None,
) -> Path:
    """Export annotations to COCO JSON format.

    Args:
        annotations_path: Path to annotations.jsonl file
        out_dir: Output directory where images are stored (for reading image dimensions)
        output_path: Optional output path for COCO JSON (default: exports/coco.json in out_dir)

    Returns:
        Path to the created COCO JSON file
    """
    # Load annotations
    annotations = load_annotations(annotations_path)

    # Build COCO dataset
    coco_dataset = build_coco_dataset(annotations, out_dir)

    # Determine output path
    if output_path is None:
        exports_dir = out_dir / "exports"
        exports_dir.mkdir(parents=True, exist_ok=True)
        output_path = exports_dir / "coco.json"
    else:
        output_path.parent.mkdir(parents=True, exist_ok=True)

    # Write COCO JSON
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(coco_dataset, f, indent=2, ensure_ascii=False)

    return output_path
