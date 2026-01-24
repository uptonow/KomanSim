# Canonical Annotations

## Overview

Structured, machine-readable annotations stored in `annotations.jsonl` (one JSON object per line).

## Format

Each line in `annotations.jsonl` contains:
```json
{
  "frame_id": "000000",
  "objects": [
    {
      "instance_id": 1,
      "bbox_xyxy": [x_min, y_min, x_max, y_max],
      "category_name": "object",
      "category_id": 1,
      "class_id": 1,
      "area": 1000
    }
  ]
}
```

## Labelers

**Bbox from Seg** (`simdata/pipeline/labelers/bbox_from_seg.py`):
- Extracts bounding boxes from segmentation masks
- Function: `bbox_from_seg(seg: np.ndarray, min_area: int = 1) -> List[Dict]`
- Input: Segmentation mask (H, W) with instance_id values
- Output: List of objects with `instance_id`, `bbox_xyxy`, `area`

## Integrity Validation

Validates:
- Non-empty masks
- Bbox encloses all mask pixels
- Consistent instance IDs between mask and annotations

## Usage

Annotations are automatically generated during job execution and written to `annotations.jsonl` in the output directory.
