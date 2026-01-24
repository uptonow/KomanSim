"""Tests for bbox_from_seg labeler using synthetic segmentation arrays."""

from __future__ import annotations

import numpy as np
import pytest

from komansim.pipeline.labelers.bbox_from_seg import (
    bbox_from_seg,
    validate_bbox_encloses_mask,
    validate_integrity,
)


def test_bbox_from_seg_empty_mask():
    """Test bbox_from_seg with empty/None segmentation."""
    # None seg
    result = bbox_from_seg(None)
    assert result == []

    # Empty seg (all zeros)
    seg = np.zeros((100, 100), dtype=np.int32)
    result = bbox_from_seg(seg)
    assert result == []


def test_bbox_from_seg_single_object():
    """Test bbox_from_seg with a single object."""
    seg = np.zeros((100, 100), dtype=np.int32)

    # Create a rectangle object with instance_id=1
    seg[20:40, 30:60] = 1

    result = bbox_from_seg(seg)

    assert len(result) == 1
    obj = result[0]
    assert obj["instance_id"] == 1
    assert obj["bbox_xyxy"] == [30, 20, 60, 40]  # [x_min, y_min, x_max, y_max]
    assert obj["area"] == 20 * 30  # 600 pixels


def test_bbox_from_seg_multiple_objects():
    """Test bbox_from_seg with multiple objects."""
    seg = np.zeros((100, 100), dtype=np.int32)

    # Object 1: rectangle at top-left
    seg[10:30, 10:40] = 1

    # Object 2: rectangle at bottom-right
    seg[60:90, 50:80] = 2

    # Object 3: small square in middle
    seg[40:50, 40:50] = 3

    result = bbox_from_seg(seg)

    assert len(result) == 3

    # Sort by instance_id for consistent ordering
    result.sort(key=lambda x: x["instance_id"])

    assert result[0]["instance_id"] == 1
    assert result[0]["bbox_xyxy"] == [10, 10, 40, 30]  # Exclusive max
    assert result[0]["area"] == 20 * 30

    assert result[1]["instance_id"] == 2
    assert result[1]["bbox_xyxy"] == [50, 60, 80, 90]  # Exclusive max
    assert result[1]["area"] == 30 * 30

    assert result[2]["instance_id"] == 3
    assert result[2]["bbox_xyxy"] == [40, 40, 50, 50]  # Exclusive max
    assert result[2]["area"] == 10 * 10


def test_bbox_from_seg_min_area_filter():
    """Test bbox_from_seg filters objects by minimum area."""
    seg = np.zeros((100, 100), dtype=np.int32)

    # Large object
    seg[10:50, 10:50] = 1

    # Small object (should be filtered)
    seg[60:62, 60:62] = 2  # 2x2 = 4 pixels

    # Medium object
    seg[70:75, 70:75] = 3  # 5x5 = 25 pixels

    # With min_area=10, object 2 should be filtered
    result = bbox_from_seg(seg, min_area=10)
    assert len(result) == 2

    instance_ids = {obj["instance_id"] for obj in result}
    assert 1 in instance_ids
    assert 2 not in instance_ids  # Filtered out
    assert 3 in instance_ids

    # With min_area=30, only object 1 should remain
    result = bbox_from_seg(seg, min_area=30)
    assert len(result) == 1
    assert result[0]["instance_id"] == 1


def test_bbox_from_seg_irregular_shape():
    """Test bbox_from_seg with irregular (non-rectangular) object shapes."""
    seg = np.zeros((100, 100), dtype=np.int32)

    # Create an L-shaped object
    seg[10:30, 20:40] = 1  # Vertical bar
    seg[30:50, 20:30] = 1  # Horizontal bar

    result = bbox_from_seg(seg)

    assert len(result) == 1
    obj = result[0]
    # Bbox should encompass the entire L-shape (exclusive max)
    assert obj["bbox_xyxy"] == [20, 10, 40, 50]  # Exclusive max
    # Area should be sum of both parts
    assert obj["area"] == (20 * 20) + (20 * 10)  # 400 + 200 = 600


def test_bbox_from_seg_non_contiguous():
    """Test bbox_from_seg with non-contiguous objects (same instance_id)."""
    seg = np.zeros((100, 100), dtype=np.int32)

    # Two separate regions with same instance_id
    seg[10:20, 10:20] = 1
    seg[50:60, 50:60] = 1

    result = bbox_from_seg(seg)

    # Should treat as single object with bbox covering both regions
    assert len(result) == 1
    obj = result[0]
    assert obj["instance_id"] == 1
    assert obj["bbox_xyxy"] == [10, 10, 60, 60]  # Encompasses both regions (exclusive max)
    assert obj["area"] == 200  # 10*10 + 10*10 = 200


def test_validate_bbox_encloses_mask():
    """Test validate_bbox_encloses_mask function."""
    seg = np.zeros((100, 100), dtype=np.int32)
    seg[20:40, 30:60] = 1

    # Valid bbox (exclusive max)
    assert validate_bbox_encloses_mask(seg, 1, [30, 20, 60, 40]) is True

    # Bbox too small (doesn't enclose)
    assert validate_bbox_encloses_mask(seg, 1, [30, 20, 50, 35]) is False

    # Bbox shifted (doesn't enclose)
    assert validate_bbox_encloses_mask(seg, 1, [40, 30, 70, 50]) is False

    # Bbox too large (but still encloses - should be True)
    assert validate_bbox_encloses_mask(seg, 1, [25, 15, 65, 45]) is True


def test_validate_integrity_valid():
    """Test validate_integrity with valid objects."""
    seg = np.zeros((100, 100), dtype=np.int32)
    seg[10:30, 10:40] = 1
    seg[60:90, 50:80] = 2

    objects = [
        {"instance_id": 1, "bbox_xyxy": [10, 10, 40, 30], "area": 600},
        {"instance_id": 2, "bbox_xyxy": [50, 60, 80, 90], "area": 900},
    ]

    is_valid, errors = validate_integrity(seg, objects)
    assert is_valid is True
    assert len(errors) == 0


def test_validate_integrity_missing_instance():
    """Test validate_integrity detects missing instance IDs."""
    seg = np.zeros((100, 100), dtype=np.int32)
    seg[10:30, 10:40] = 1
    seg[60:90, 50:80] = 2

    # Object with instance_id not in seg
    objects = [
        {"instance_id": 1, "bbox_xyxy": [10, 10, 40, 30], "area": 600},
        {"instance_id": 3, "bbox_xyxy": [50, 60, 80, 90], "area": 900},  # Not in seg
    ]

    is_valid, errors = validate_integrity(seg, objects)
    assert is_valid is False
    assert any("instance_id 3" in e for e in errors)


def test_validate_integrity_bbox_not_enclosing():
    """Test validate_integrity detects bbox that doesn't enclose mask."""
    seg = np.zeros((100, 100), dtype=np.int32)
    seg[10:30, 10:40] = 1

    # Bbox too small
    objects = [
        {"instance_id": 1, "bbox_xyxy": [10, 10, 30, 25], "area": 300},  # Doesn't enclose
    ]

    is_valid, errors = validate_integrity(seg, objects)
    assert is_valid is False
    assert any("does not enclose" in e for e in errors)


def test_validate_integrity_missing_objects():
    """Test validate_integrity detects missing objects for instance IDs in seg."""
    seg = np.zeros((100, 100), dtype=np.int32)
    seg[10:30, 10:40] = 1
    seg[60:90, 50:80] = 2

    # Only one object, but seg has two instances
    objects = [
        {"instance_id": 1, "bbox_xyxy": [10, 10, 40, 30], "area": 600},
    ]

    is_valid, errors = validate_integrity(seg, objects)
    assert is_valid is False
    assert any("instance IDs" in e and "2" in e for e in errors)


def test_bbox_from_seg_invalid_shape():
    """Test bbox_from_seg raises error for invalid seg shape."""
    # 3D array
    seg = np.zeros((10, 10, 3), dtype=np.int32)
    with pytest.raises(ValueError, match="must be 2D array"):
        bbox_from_seg(seg)

    # 1D array
    seg = np.zeros((100,), dtype=np.int32)
    with pytest.raises(ValueError, match="must be 2D array"):
        bbox_from_seg(seg)


def test_bbox_from_seg_edge_cases():
    """Test bbox_from_seg with edge cases."""
    # Single pixel object
    seg = np.zeros((100, 100), dtype=np.int32)
    seg[50, 50] = 1

    result = bbox_from_seg(seg, min_area=1)
    assert len(result) == 1
    # Our implementation uses exclusive max coordinates (standard format)
    # For a single pixel at (50, 50), bbox is [50, 50, 51, 51]
    assert result[0]["bbox_xyxy"] == [50, 50, 51, 51]
    assert result[0]["area"] == 1

    # Object at image edges
    seg = np.zeros((100, 100), dtype=np.int32)
    seg[0:10, 0:10] = 1  # Top-left corner
    seg[90:100, 90:100] = 2  # Bottom-right corner

    result = bbox_from_seg(seg)
    assert len(result) == 2
    result.sort(key=lambda x: x["instance_id"])
    assert result[0]["bbox_xyxy"] == [0, 0, 10, 10]  # Exclusive max
    assert result[1]["bbox_xyxy"] == [90, 90, 100, 100]  # Exclusive max
