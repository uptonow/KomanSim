"""Dataset QA and preview generation.

This module generates quality assurance statistics and preview images for datasets.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional

import imageio.v2 as imageio
import numpy as np


def generate_previews(
    out_dir: Path,
    num_previews: int = 8,
    max_size: int = 512,
) -> Path:
    """Generate preview images from first N RGB frames.

    Args:
        out_dir: Output directory containing rgb/ directory
        num_previews: Number of preview images to generate (default: 8)
        max_size: Maximum size on the long side in pixels (default: 512)

    Returns:
        Path to previews directory
    """
    rgb_dir = out_dir / "rgb"
    previews_dir = out_dir / "previews"

    if not rgb_dir.exists():
        return previews_dir

    previews_dir.mkdir(exist_ok=True)

    # Find all RGB images
    rgb_files = sorted(rgb_dir.glob("*.png"))
    if not rgb_files:
        return previews_dir

    # Take first N frames
    num_to_generate = min(num_previews, len(rgb_files))

    for i, rgb_file in enumerate(rgb_files[:num_to_generate]):
        try:
            # Load image
            img = imageio.imread(rgb_file)

            # Downscale if needed
            h, w = img.shape[:2]
            long_side = max(h, w)

            if long_side > max_size:
                scale = max_size / long_side
                new_h = int(h * scale)
                new_w = int(w * scale)
                # Simple downscaling using numpy (nearest neighbor)
                # For better quality, could use scipy.ndimage.zoom, but keep it lightweight
                if len(img.shape) == 3:
                    # RGB image
                    y_indices = np.round(np.linspace(0, h - 1, new_h)).astype(int)
                    x_indices = np.round(np.linspace(0, w - 1, new_w)).astype(int)
                    img = img[y_indices[:, None], x_indices]
                else:
                    # Grayscale
                    y_indices = np.round(np.linspace(0, h - 1, new_h)).astype(int)
                    x_indices = np.round(np.linspace(0, w - 1, new_w)).astype(int)
                    img = img[y_indices[:, None], x_indices]

            # Save preview (use jpg for smaller size)
            preview_name = f"preview_{i:03d}.jpg"
            preview_path = previews_dir / preview_name
            imageio.imwrite(preview_path, img, quality=85)
        except Exception:
            # Skip frames that can't be loaded
            continue

    return previews_dir


def generate_qa(
    annotations_jsonl_path: Path,
    out_path: Path,
    previews_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Generate QA statistics from annotations.jsonl.

    Args:
        annotations_jsonl_path: Path to annotations.jsonl file
        out_path: Path where qa.json will be written
        previews_dir: Optional path to previews directory

    Returns:
        Dictionary containing QA statistics
    """
    # Load annotations
    annotations: List[Dict[str, Any]] = []
    with open(annotations_jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                annotations.append(json.loads(line))

    # Compute statistics
    frame_ids = set()
    num_annotations_total = 0
    per_class_counts: Dict[str, int] = {}
    bbox_areas_by_class: Dict[str, List[float]] = {}

    for ann in annotations:
        frame_id = ann.get("frame_id")
        if frame_id is not None:
            frame_ids.add(frame_id)

        objects = ann.get("objects", [])
        num_annotations_total += len(objects)

        for obj in objects:
            # Get class identifier (prefer category_name, fallback to category_id, then class_id)
            # Use stable string keys instead of Python hash()
            class_key = None
            if "category_name" in obj:
                class_key = obj["category_name"]
            elif "category_id" in obj:
                class_key = str(obj["category_id"])
            elif "class_id" in obj:
                class_key = str(obj["class_id"])

            # If no class identifier found, skip this object
            if class_key is None:
                continue

            per_class_counts[class_key] = per_class_counts.get(class_key, 0) + 1

            # Compute bbox area
            bbox = obj.get("bbox_xyxy")
            if bbox and isinstance(bbox, list) and len(bbox) == 4:
                x_min, y_min, x_max, y_max = bbox
                width = x_max - x_min
                height = y_max - y_min
                area = width * height

                if class_key not in bbox_areas_by_class:
                    bbox_areas_by_class[class_key] = []
                bbox_areas_by_class[class_key].append(area)

    # Compute bbox area stats per class
    bbox_stats_by_class: Dict[str, Dict[str, float]] = {}
    for class_key, areas in bbox_areas_by_class.items():
        if not areas:
            continue

        sorted_areas = sorted(areas)
        n = len(sorted_areas)

        bbox_stats_by_class[class_key] = {
            "min": float(min(areas)),
            "median": float(sorted_areas[n // 2] if n > 0 else 0.0),
            "max": float(max(areas)),
            "p90": float(sorted_areas[int(math.ceil(n * 0.9)) - 1] if n > 0 else 0.0),
        }

    # Build QA dictionary
    qa_data: Dict[str, Any] = {
        "frames_generated": len(frame_ids),
        "num_annotations_total": num_annotations_total,
        "per_class_counts": per_class_counts,  # Already string keys
        "bbox_area_stats_per_class": bbox_stats_by_class,  # Already string keys
    }

    # Add previews list if previews_dir exists
    if previews_dir is not None and previews_dir.exists():
        preview_files = sorted(previews_dir.glob("*.jpg")) + sorted(previews_dir.glob("*.png"))
        # Get relative paths from out_path parent (dataset root)
        dataset_root = out_path.parent
        previews_list = []
        for preview_file in preview_files:
            try:
                rel_path = preview_file.relative_to(dataset_root).as_posix()
                previews_list.append(rel_path)
            except ValueError:
                # Skip if preview is outside dataset root
                continue
        qa_data["previews"] = previews_list

    # Write qa.json
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(qa_data, f, indent=2, ensure_ascii=False)

    return qa_data
