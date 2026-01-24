# QA and Previews

## Overview

Generates quality assurance statistics and preview images for datasets.

## QA Generation

**Function:** `generate_qa(annotations_jsonl_path: Path, out_path: Path) -> Dict`

Generates `qa.json` with:
- `frames_generated`: Number of frames
- `num_annotations_total`: Total annotations
- `per_class_counts`: Annotation counts per class
- `bbox_area_stats_per_class`: Min/median/max/p90 bbox areas per class

## Preview Generation

**Function:** `generate_previews(out_dir: Path, num_previews: int = 8, max_size: int = 512) -> Path`

Generates preview images:
- Samples frames from dataset
- Resizes to max_size (default 512px)
- Saves to `previews/` directory
- Returns path to previews directory

## Integration

QA and previews are automatically generated after job completion. No manual steps required.
