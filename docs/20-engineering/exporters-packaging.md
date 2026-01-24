# Exporters and Packaging

## Overview

Converts canonical annotations to COCO/YOLO formats and packages datasets for distribution.

## Architecture

```
annotations.jsonl → COCO/YOLO exports → Package (zip/tar)
```

## COCO Exporter

**Function:** `export_coco(annotations_path: Path, out_dir: Path) -> Path`

Converts canonical annotations to COCO JSON format:
- **Input**: `annotations.jsonl` (canonical format)
- **Output**: `exports/coco/annotations.json` (COCO format)
- **Bbox conversion**: `[x_min, y_min, x_max, y_max]` → `[x, y, width, height]`

**COCO structure:**
```json
{
  "images": [...],
  "annotations": [...],
  "categories": [...]
}
```

## YOLO Exporter

**Function:** `export_yolo(annotations_path: Path, out_dir: Path) -> Path`

Converts canonical annotations to YOLO txt format:
- **Input**: `annotations.jsonl` (canonical format)
- **Output**: `exports/yolo/labels/*.txt` (one file per frame)
- **Bbox format**: Normalized `[center_x, center_y, width, height]` (0-1 range)
- **Label format**: `class_id center_x center_y width height`

## Package Creation

**Function:** `create_package(out_dir: Path, format: "zip" | "tar" = "zip") -> Path`

Creates compressed archive at `{out_dir}.zip` (sibling of out_dir).

**Package contents:**
- `manifest.json` (required)
- `annotations.jsonl` (required)
- `exports/` directory (COCO + YOLO)
- `previews/` directory (optional)

## Integration

Exports and packaging are automatic after job completion. No manual steps required.
