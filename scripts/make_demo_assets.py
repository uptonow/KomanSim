#!/usr/bin/env python3
"""Generate demo visualization from COCO export.

Creates a visualization showing class distribution and bbox area histogram
from a COCO annotations.json file.
"""

import argparse
import json
from pathlib import Path

try:
    import matplotlib

    matplotlib.use("Agg")  # Non-interactive backend
    import matplotlib.pyplot as plt

    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False
    try:
        from PIL import Image, ImageDraw, ImageFont

        HAS_PILLOW = True
    except ImportError:
        HAS_PILLOW = False


def load_coco_annotations(coco_path: Path) -> dict:
    """Load COCO annotations JSON file."""
    with open(coco_path, "r", encoding="utf-8") as f:
        return json.load(f)


def generate_visualization_matplotlib(coco_data: dict, output_path: Path) -> None:
    """Generate visualization using matplotlib (preferred)."""
    categories = coco_data.get("categories", [])
    annotations = coco_data.get("annotations", [])

    # Extract class distribution
    class_counts = {}
    for cat in categories:
        class_counts[cat["id"]] = 0

    for ann in annotations:
        cat_id = ann["category_id"]
        class_counts[cat_id] = class_counts.get(cat_id, 0) + 1

    # Extract bbox areas
    areas = [ann["area"] for ann in annotations]

    # Create figure with two subplots
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

    # Class distribution bar chart
    if class_counts:
        class_ids = sorted(class_counts.keys())
        class_names = [f"class_{cid}" for cid in class_ids]
        counts = [class_counts[cid] for cid in class_ids]

        ax1.bar(class_names, counts, color="steelblue", edgecolor="black")
        ax1.set_xlabel("Class")
        ax1.set_ylabel("Count")
        ax1.set_title("Class Distribution")
        ax1.tick_params(axis="x", rotation=45)
        ax1.grid(axis="y", alpha=0.3)
    else:
        ax1.text(0.5, 0.5, "No annotations", ha="center", va="center", transform=ax1.transAxes)
        ax1.set_title("Class Distribution")

    # Bbox area histogram
    if areas:
        ax2.hist(areas, bins=20, color="coral", edgecolor="black", alpha=0.7)
        ax2.set_xlabel("Bounding Box Area (pixels²)")
        ax2.set_ylabel("Frequency")
        ax2.set_title("Bounding Box Area Distribution")
        ax2.grid(axis="y", alpha=0.3)
    else:
        ax2.text(0.5, 0.5, "No annotations", ha="center", va="center", transform=ax2.transAxes)
        ax2.set_title("Bounding Box Area Distribution")

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()


def generate_visualization_pillow(coco_data: dict, output_path: Path) -> None:
    """Generate simple visualization using Pillow (fallback)."""
    categories = coco_data.get("categories", [])
    annotations = coco_data.get("annotations", [])

    # Extract class distribution
    class_counts = {}
    for cat in categories:
        class_counts[cat["id"]] = 0

    for ann in annotations:
        cat_id = ann["category_id"]
        class_counts[cat_id] = class_counts.get(cat_id, 0) + 1

    # Create a simple text-based visualization
    img = Image.new("RGB", (800, 600), color="white")
    draw = ImageDraw.Draw(img)

    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16)
        title_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 20)
    except Exception:
        font = ImageFont.load_default()
        title_font = ImageFont.load_default()

    y = 30
    draw.text((20, y), "COCO Export Statistics", fill="black", font=title_font)
    y += 50

    draw.text((20, y), f"Total annotations: {len(annotations)}", fill="black", font=font)
    y += 30
    draw.text((20, y), f"Total categories: {len(categories)}", fill="black", font=font)
    y += 40

    draw.text((20, y), "Class Distribution:", fill="black", font=title_font)
    y += 30

    for cat_id in sorted(class_counts.keys()):
        count = class_counts[cat_id]
        draw.text((40, y), f"class_{cat_id}: {count}", fill="black", font=font)
        y += 25

    img.save(output_path)


def main():
    parser = argparse.ArgumentParser(description="Generate demo visualization from COCO export")
    parser.add_argument(
        "--annotations", type=Path, required=True, help="Path to COCO annotations.json file"
    )
    parser.add_argument("--out", type=Path, required=True, help="Output path for PNG image")
    args = parser.parse_args()

    if not args.annotations.exists():
        raise FileNotFoundError(f"Annotations file not found: {args.annotations}")

    # Load COCO data
    coco_data = load_coco_annotations(args.annotations)

    # Ensure output directory exists
    args.out.parent.mkdir(parents=True, exist_ok=True)

    # Generate visualization
    if HAS_MATPLOTLIB:
        generate_visualization_matplotlib(coco_data, args.out)
    elif HAS_PILLOW:
        generate_visualization_pillow(coco_data, args.out)
    else:
        raise RuntimeError(
            "Neither matplotlib nor Pillow is available. Please install one: pip install matplotlib"
        )

    print(f"Demo visualization saved to: {args.out}")


if __name__ == "__main__":
    main()
