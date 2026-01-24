"""Canonical annotations spine generation.

This module generates annotations.jsonl as the canonical truth for each frame.
Each line is a JSON object representing one frame's annotations.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

from komansim.pipeline.labelers.bbox_from_seg import bbox_from_seg, validate_integrity


def build_frame_annotation(
    frame_id: int,
    out_dir: Path,
    seg: Optional[np.ndarray] = None,
    meta: Optional[Dict[str, Any]] = None,
    min_bbox_area: int = 1,
) -> Dict[str, Any]:
    """Build annotation record for a single frame.

    Args:
        frame_id: Frame index (0-based)
        out_dir: Output directory where files are written
        seg: Optional segmentation mask of shape (H, W) with int32 values
        meta: Optional metadata dictionary (may contain camera intrinsics/extrinsics)
        min_bbox_area: Minimum area in pixels for a valid bbox

    Returns:
        Dictionary representing the frame annotation with:
        - frame_id: Frame index
        - image_path: Relative path to RGB image (if exists)
        - seg_path: Relative path to segmentation mask (if exists)
        - depth_path: Relative path to depth map (if exists, optional)
        - objects: List of object annotations
        - camera: Camera metadata if present (intrinsics/extrinsics)
    """
    frame_str = f"{frame_id:06d}"

    # Build paths relative to out_dir
    image_path = f"rgb/{frame_str}.png"
    seg_path = f"seg/{frame_str}.npy" if seg is not None else None
    depth_path = f"depth/{frame_str}.npy"

    # Check if files actually exist
    if not (out_dir / image_path).exists():
        image_path = None
    if seg_path and not (out_dir / seg_path).exists():
        seg_path = None
    if not (out_dir / depth_path).exists():
        depth_path = None

    # Extract objects from segmentation mask
    objects: List[Dict[str, Any]] = []
    if seg is not None:
        bbox_objects = bbox_from_seg(seg, min_area=min_bbox_area)

        for obj in bbox_objects:
            # Build object annotation
            object_ann = {
                "instance_id": obj["instance_id"],
                "class_id": obj["instance_id"],  # For now, use instance_id as class_id
                "bbox_xyxy": obj["bbox_xyxy"],
            }

            # Add mask reference if segmentation exists
            if seg_path:
                object_ann["mask_ref"] = {
                    "path": seg_path,
                    "instance_id": obj["instance_id"],
                }

            objects.append(object_ann)

    # Build frame annotation
    annotation: Dict[str, Any] = {
        "frame_id": frame_id,
    }

    if image_path:
        annotation["image_path"] = image_path
    if seg_path:
        annotation["seg_path"] = seg_path
    if depth_path:
        annotation["depth_path"] = depth_path

    annotation["objects"] = objects

    # Extract camera metadata from meta if present
    camera_meta: Dict[str, Any] = {}
    if meta:
        if "intrinsics" in meta:
            camera_meta["intrinsics"] = meta["intrinsics"]
        if "extrinsics" in meta:
            camera_meta["extrinsics"] = meta["extrinsics"]
        # Also check for sensor intrinsics (from job config)
        if "sensor_intrinsics" in meta:
            camera_meta["intrinsics"] = meta["sensor_intrinsics"]

    if camera_meta:
        annotation["camera"] = camera_meta

    return annotation


def write_annotations(
    annotations: List[Dict[str, Any]],
    out_dir: Path,
    validate: bool = True,
) -> None:
    """Write annotations to annotations.jsonl file.

    Args:
        annotations: List of frame annotation dictionaries
        out_dir: Output directory where annotations.jsonl will be written
        validate: If True, validate integrity of annotations before writing

    Raises:
        ValueError: If validation fails and validate=True
    """
    if validate:
        errors: List[str] = []

        # Validate each annotation
        for ann in annotations:
            frame_id = ann.get("frame_id")
            seg_path = ann.get("seg_path")
            objects = ann.get("objects", [])

            # If we have objects, we should have seg_path
            if objects and not seg_path:
                errors.append(f"Frame {frame_id}: objects present but seg_path is missing")

            # Validate objects have required fields
            for obj in objects:
                required_fields = ["instance_id", "class_id", "bbox_xyxy"]
                for field in required_fields:
                    if field not in obj:
                        errors.append(f"Frame {frame_id}: object missing required field '{field}'")

                # Validate bbox format
                bbox = obj.get("bbox_xyxy")
                if bbox and (not isinstance(bbox, list) or len(bbox) != 4):
                    errors.append(
                        f"Frame {frame_id}: invalid bbox_xyxy format (expected [x_min, y_min, x_max, y_max])"
                    )

        if errors:
            raise ValueError(
                f"Annotation validation failed with {len(errors)} errors:\n"
                + "\n".join(f"  - {e}" for e in errors)
            )

    # Write annotations.jsonl
    annotations_path = out_dir / "annotations.jsonl"
    with open(annotations_path, "w", encoding="utf-8") as f:
        for ann in annotations:
            f.write(json.dumps(ann, ensure_ascii=False) + "\n")


def generate_annotations(
    out_dir: Path,
    num_frames: int,
    seg_arrays: Optional[List[Optional[np.ndarray]]] = None,
    meta_list: Optional[List[Optional[Dict[str, Any]]]] = None,
    min_bbox_area: int = 1,
    validate_integrity_checks: bool = True,
) -> List[Dict[str, Any]]:
    """Generate annotations for all frames.

    Args:
        out_dir: Output directory where files are written
        num_frames: Number of frames to process
        seg_arrays: Optional list of segmentation arrays (one per frame)
        meta_list: Optional list of metadata dictionaries (one per frame)
        min_bbox_area: Minimum area in pixels for a valid bbox
        validate_integrity_checks: If True, run integrity checks on seg masks

    Returns:
        List of frame annotation dictionaries
    """
    annotations: List[Dict[str, Any]] = []

    for i in range(num_frames):
        seg = seg_arrays[i] if seg_arrays and i < len(seg_arrays) else None
        meta = meta_list[i] if meta_list and i < len(meta_list) else None

        # Build annotation for this frame
        ann = build_frame_annotation(
            frame_id=i,
            out_dir=out_dir,
            seg=seg,
            meta=meta,
            min_bbox_area=min_bbox_area,
        )

        # Run integrity checks if requested and seg is available
        if validate_integrity_checks and seg is not None:
            objects = ann.get("objects", [])
            is_valid, errors = validate_integrity(seg, objects)

            if not is_valid:
                # Log errors but don't fail - integrity issues are warnings
                # In production, you might want to skip frames with integrity issues
                print(f"Warning: Frame {i} integrity check failed:")
                for error in errors:
                    print(f"  - {error}")

        annotations.append(ann)

    return annotations
