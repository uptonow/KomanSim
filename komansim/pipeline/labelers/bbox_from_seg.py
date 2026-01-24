"""Labeler that derives bounding boxes from segmentation masks."""

from __future__ import annotations

from typing import Dict, List, Tuple

import numpy as np


def bbox_from_seg(
    seg: np.ndarray,
    min_area: int = 1,
) -> List[Dict[str, int]]:
    """Extract bounding boxes from segmentation mask.

    Args:
        seg: Segmentation mask of shape (H, W) with int32 values.
            Each pixel value represents an instance_id (0 = background).
        min_area: Minimum number of pixels required for a valid object.
            Objects with fewer pixels will be filtered out.

    Returns:
        List of object dictionaries, each containing:
        - instance_id: The instance ID from the segmentation mask
        - bbox_xyxy: Bounding box as [x_min, y_min, x_max, y_max]
        - area: Number of pixels in the mask

    Note:
        - Background pixels (value 0) are ignored
        - Each unique non-zero value in seg is treated as a separate instance
        - Bounding boxes are computed as the axis-aligned bounding box of all
          pixels belonging to each instance
    """
    if seg is None:
        return []

    if seg.ndim != 2:
        raise ValueError(f"seg must be 2D array (H, W), got shape {seg.shape}")

    objects: List[Dict[str, int]] = []

    # Get unique instance IDs (excluding background = 0)
    unique_ids = np.unique(seg)
    unique_ids = unique_ids[unique_ids != 0]

    for instance_id in unique_ids:
        # Create binary mask for this instance
        mask = seg == instance_id

        # Check if mask is non-empty
        if not np.any(mask):
            continue

        # Find bounding box coordinates
        rows = np.where(mask)[0]
        cols = np.where(mask)[1]

        if len(rows) == 0 or len(cols) == 0:
            continue

        y_min = int(np.min(rows))
        y_max = int(np.max(rows))
        x_min = int(np.min(cols))
        x_max = int(np.max(cols))

        area = len(rows)

        # Filter by minimum area
        if area < min_area:
            continue

        # bbox_xyxy format: [x_min, y_min, x_max, y_max] with exclusive max
        # Add 1 to max coordinates to make them exclusive (standard format)
        objects.append(
            {
                "instance_id": int(instance_id),
                "bbox_xyxy": [x_min, y_min, x_max + 1, y_max + 1],
                "area": area,
            }
        )

    return objects


def validate_bbox_encloses_mask(
    seg: np.ndarray,
    instance_id: int,
    bbox_xyxy: List[int],
) -> bool:
    """Validate that bounding box encloses all mask pixels.

    Args:
        seg: Segmentation mask of shape (H, W)
        instance_id: Instance ID to check
        bbox_xyxy: Bounding box as [x_min, y_min, x_max, y_max]

    Returns:
        True if bbox encloses all mask pixels, False otherwise
    """
    if seg is None:
        return False

    x_min, y_min, x_max, y_max = bbox_xyxy

    # Get mask for this instance
    mask = seg == instance_id

    if not np.any(mask):
        return False

    # Check that all mask pixels are within bbox
    rows = np.where(mask)[0]
    cols = np.where(mask)[1]

    if len(rows) == 0 or len(cols) == 0:
        return False

    # bbox_xyxy uses exclusive max, so pixels should be < y_max and < x_max
    # All rows should be >= y_min and < y_max
    # All cols should be >= x_min and < x_max
    if np.any(rows < y_min) or np.any(rows >= y_max):
        return False
    if np.any(cols < x_min) or np.any(cols >= x_max):
        return False

    return True


def validate_integrity(
    seg: np.ndarray,
    objects: List[Dict[str, int]],
) -> Tuple[bool, List[str]]:
    """Validate integrity of objects derived from segmentation mask.

    Checks:
    1. Each object has a non-empty mask
    2. Each bbox encloses all mask pixels
    3. Instance IDs are consistent (present in seg)

    Args:
        seg: Segmentation mask of shape (H, W)
        objects: List of object dictionaries with instance_id and bbox_xyxy

    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    errors: List[str] = []

    if seg is None:
        errors.append("seg is None")
        return False, errors

    # Get all instance IDs in the segmentation mask
    unique_ids_in_seg = set(np.unique(seg))
    unique_ids_in_seg.discard(0)  # Remove background

    # Check each object
    for obj in objects:
        instance_id = obj["instance_id"]
        bbox_xyxy = obj["bbox_xyxy"]

        # Check 1: Instance ID exists in seg
        if instance_id not in unique_ids_in_seg:
            errors.append(f"Object instance_id {instance_id} not found in segmentation mask")
            continue

        # Check 2: Mask is non-empty
        mask = seg == instance_id
        if not np.any(mask):
            errors.append(f"Object instance_id {instance_id} has empty mask")
            continue

        # Check 3: Bbox encloses mask pixels
        if not validate_bbox_encloses_mask(seg, instance_id, bbox_xyxy):
            errors.append(
                f"Object instance_id {instance_id} bbox {bbox_xyxy} does not enclose all mask pixels"
            )

    # Check for consistency: all non-zero IDs in seg should have objects
    object_ids = {obj["instance_id"] for obj in objects}
    missing_ids = unique_ids_in_seg - object_ids
    if missing_ids:
        errors.append(
            f"Segmentation mask contains instance IDs {sorted(missing_ids)} that are not in objects list"
        )

    return len(errors) == 0, errors
