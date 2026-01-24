#!/usr/bin/env python3
"""Generate demo visualization from YOLO export.

Creates a visualization showing YOLO bounding boxes drawn on blank canvases
for sample images from the dataset.
"""

import argparse
import yaml
from pathlib import Path

try:
    import matplotlib

    matplotlib.use("Agg")  # Non-interactive backend
    import matplotlib.pyplot as plt
    import matplotlib.patches as patches
    import numpy as np

    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False
    try:
        from PIL import Image, ImageDraw, ImageFont

        HAS_PILLOW = True
    except ImportError:
        HAS_PILLOW = False


def load_dataset_yaml(dataset_yaml_path: Path) -> dict:
    """Load YOLO dataset.yaml file."""
    with open(dataset_yaml_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_yolo_label(label_path: Path) -> list:
    """Load YOLO label file and return list of (class_id, x_center, y_center, width, height)."""
    annotations = []
    if not label_path.exists():
        return annotations

    with open(label_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) >= 5:
                try:
                    class_id = int(parts[0])
                    x_center = float(parts[1])
                    y_center = float(parts[2])
                    width = float(parts[3])
                    height = float(parts[4])

                    # Verify normalization
                    if not (
                        0 <= x_center <= 1
                        and 0 <= y_center <= 1
                        and 0 <= width <= 1
                        and 0 <= height <= 1
                    ):
                        continue

                    annotations.append((class_id, x_center, y_center, width, height))
                except ValueError:
                    continue

    return annotations


def generate_stats_chart(dataset_yaml: dict, labels_dir: Path, output_path: Path) -> None:
    """Generate a summary chart when no objects are detected."""
    # Count total files
    label_files = list(labels_dir.glob("*.txt"))
    total_files = len(label_files)

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.axis("off")

    # Title
    ax.text(
        0.5,
        0.9,
        "YOLO Dataset Stats (Dummy Backend)",
        ha="center",
        va="center",
        fontsize=20,
        weight="bold",
    )

    # Stats
    stats_text = (
        f"Total Images: {total_files}\n"
        f"Total Objects: 0\n"
        f"Classes Detected: None\n\n"
        "Note: The dummy backend generates placeholder images\n"
        "without objects by default. Use a physics backend\n"
        "(MuJoCo, PyBullet, Isaac Sim) to generate valid labels."
    )

    ax.text(
        0.5,
        0.5,
        stats_text,
        ha="center",
        va="center",
        fontsize=14,
        bbox=dict(boxstyle="round,pad=1", facecolor="white", alpha=0.9, edgecolor="gray"),
    )

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()


def draw_bboxes_matplotlib(
    dataset_yaml: dict,
    labels_dir: Path,
    n_samples: int,
    img_width: int,
    img_height: int,
    output_path: Path,
) -> None:
    """Generate visualization using matplotlib (preferred)."""
    # Get class names mapping
    names = dataset_yaml.get("names", {})

    # Find label files (sorted for deterministic selection)
    label_files = sorted(labels_dir.glob("*.txt"))

    # First, check if we have ANY objects at all
    total_objects = 0
    for lf in label_files:
        anns = load_yolo_label(lf)
        total_objects += len(anns)

    # Fallback to stats chart if no objects found across all files
    if total_objects == 0:
        generate_stats_chart(dataset_yaml, labels_dir, output_path)
        return

    # Select samples
    selected_files = label_files[:n_samples]

    # Calculate grid layout
    n_cols = min(3, len(selected_files))
    n_rows = (len(selected_files) + n_cols - 1) // n_cols

    fig, axes = plt.subplots(n_rows, n_cols, figsize=(n_cols * 5, n_rows * 4))
    if len(selected_files) == 1:
        axes = [axes]
    elif n_rows == 1:
        axes = axes if isinstance(axes, list) else [axes]
    else:
        axes = axes.flatten()

    for idx, label_file in enumerate(selected_files):
        ax = axes[idx] if idx < len(axes) else axes[-1]

        # Create blank white canvas
        ax.imshow(np.ones((img_height, img_width, 3), dtype=np.uint8) * 255)

        # Load annotations
        annotations = load_yolo_label(label_file)

        if not annotations:
            # Draw warning text
            ax.text(
                img_width / 2,
                img_height / 2,
                "No valid boxes",
                ha="center",
                va="center",
                color="gray",
                fontsize=12,
            )

        # Draw bounding boxes
        for class_id, x_center, y_center, width, height in annotations:
            # Convert normalized coordinates to pixel coordinates
            # x_center_px = x_center * img_width
            # y_center_px = y_center * img_height
            width_px = width * img_width
            height_px = height * img_height

            # Calculate top-left corner
            x_min = (x_center * img_width) - (width_px / 2)
            y_min = (y_center * img_height) - (height_px / 2)

            # Draw rectangle
            rect = patches.Rectangle(
                (x_min, y_min), width_px, height_px, linewidth=3, edgecolor="red", facecolor="none"
            )
            ax.add_patch(rect)

            # Add class label
            class_name = names.get(class_id, f"class_{class_id}")
            ax.text(
                x_min,
                y_min - 5,
                class_name,
                fontsize=10,
                color="white",
                weight="bold",
                bbox=dict(boxstyle="square,pad=0.2", facecolor="red", alpha=1.0, edgecolor="none"),
            )

        # Set title
        ax.set_title(f"{label_file.name}", fontsize=10)
        ax.axis("off")
        ax.set_xlim(0, img_width)
        ax.set_ylim(img_height, 0)  # Invert Y axis

    # Hide unused subplots
    for idx in range(len(selected_files), len(axes)):
        axes[idx].axis("off")

    plt.suptitle("YOLO Labels Visualization (dummy backend)", fontsize=14, y=0.99)
    plt.tight_layout(pad=1.0, rect=[0, 0, 1, 0.96])
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()

    # Self-check
    check_output_image(output_path)


def draw_bboxes_pillow(
    dataset_yaml: dict,
    labels_dir: Path,
    n_samples: int,
    img_width: int,
    img_height: int,
    output_path: Path,
) -> None:
    """Generate simple visualization using Pillow (fallback)."""
    # Get class names mapping
    names = dataset_yaml.get("names", {})

    # Find label files (sorted for deterministic selection)
    label_files = sorted(labels_dir.glob("*.txt"))

    # First, check if we have ANY objects at all
    total_objects = 0
    for lf in label_files:
        anns = load_yolo_label(lf)
        total_objects += len(anns)

    if total_objects == 0:
        # Generate simple stats image
        img = Image.new("RGB", (800, 400), color="white")
        draw = ImageDraw.Draw(img)
        draw.text((400, 200), "YOLO Dataset Stats: 0 Objects Detected", fill="black", anchor="mm")
        img.save(output_path)
        return

    # Select samples
    selected_files = label_files[:n_samples]

    # Create a grid of images
    n_cols = min(3, len(selected_files))
    n_rows = (len(selected_files) + n_cols - 1) // n_cols

    cell_width = img_width
    cell_height = img_height + 30  # Extra space for label

    canvas_width = n_cols * cell_width
    canvas_height = n_rows * cell_height

    img = Image.new("RGB", (canvas_width, canvas_height), color="white")
    draw = ImageDraw.Draw(img)

    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 12)
        title_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 14)
    except Exception:
        font = ImageFont.load_default()
        title_font = ImageFont.load_default()

    for idx, label_file in enumerate(selected_files):
        row = idx // n_cols
        col = idx % n_cols

        x_offset = col * cell_width
        y_offset = row * cell_height

        # Create blank white canvas for this sample
        sample_img = Image.new("RGB", (img_width, img_height), color="white")
        sample_draw = ImageDraw.Draw(sample_img)

        # Load annotations
        annotations = load_yolo_label(label_file)

        if not annotations:
            sample_draw.text(
                (img_width / 2, img_height / 2), "No valid boxes", fill="gray", anchor="mm"
            )

        # Draw bounding boxes
        for class_id, x_center, y_center, width, height in annotations:
            width_px = width * img_width
            height_px = height * img_height

            x_min = (x_center * img_width) - (width_px / 2)
            y_min = (y_center * img_height) - (height_px / 2)
            x_max = x_min + width_px
            y_max = y_min + height_px

            # Draw rectangle
            sample_draw.rectangle([x_min, y_min, x_max, y_max], outline="red", width=3)

            # Add class label
            class_name = names.get(class_id, f"class_{class_id}")
            sample_draw.text((x_min, y_min - 15), class_name, fill="red", font=font)

        # Paste sample onto canvas
        img.paste(sample_img, (x_offset, y_offset))

        # Add filename label below
        draw.text(
            (x_offset + cell_width // 2, y_offset + img_height + 10),
            label_file.name,
            fill="black",
            font=title_font,
            anchor="mm",
        )

    img.save(output_path)
    check_output_image(output_path)


def check_output_image(output_path: Path) -> None:
    """Verify output image is not mostly white."""
    if not HAS_PILLOW:
        return

    try:
        with Image.open(output_path) as img:
            # Convert to grayscale
            gray = img.convert("L")
            # Calculate mean pixel value
            mean_val = (
                np.mean(np.array(gray)) if HAS_MATPLOTLIB else 255
            )  # Fallback if numpy missing

            if mean_val > 252:
                print(f"Warning: Generated image seems mostly empty (mean: {mean_val:.1f})")
    except Exception as e:
        print(f"Warning: Could not verify output image: {e}")


def main():
    parser = argparse.ArgumentParser(description="Generate demo visualization from YOLO export")
    parser.add_argument(
        "--dataset_yaml", type=Path, required=True, help="Path to YOLO dataset.yaml file"
    )
    parser.add_argument("--out", type=Path, required=True, help="Output path for PNG image")
    parser.add_argument("--n", type=int, default=6, help="Number of samples to draw (default: 6)")
    parser.add_argument(
        "--imgw", type=int, default=640, help="Image width in pixels (default: 640)"
    )
    parser.add_argument(
        "--imgh", type=int, default=480, help="Image height in pixels (default: 480)"
    )
    args = parser.parse_args()

    if not args.dataset_yaml.exists():
        raise FileNotFoundError(f"Dataset YAML file not found: {args.dataset_yaml}")

    # Load dataset YAML
    dataset_yaml = load_dataset_yaml(args.dataset_yaml)

    # Determine labels directory (prefer train, fallback to val)
    dataset_root = args.dataset_yaml.parent
    labels_train_dir = dataset_root / "labels" / "train"
    labels_val_dir = dataset_root / "labels" / "val"

    labels_dir = labels_train_dir if labels_train_dir.exists() else labels_val_dir
    if not labels_dir.exists():
        raise FileNotFoundError(f"Labels directory not found: {labels_dir}")

    # Ensure output directory exists
    args.out.parent.mkdir(parents=True, exist_ok=True)

    # Generate visualization
    if HAS_MATPLOTLIB:
        draw_bboxes_matplotlib(dataset_yaml, labels_dir, args.n, args.imgw, args.imgh, args.out)
    elif HAS_PILLOW:
        draw_bboxes_pillow(dataset_yaml, labels_dir, args.n, args.imgw, args.imgh, args.out)
    else:
        raise RuntimeError(
            "Neither matplotlib nor Pillow is available. Please install one: pip install matplotlib"
        )

    print(f"YOLO demo visualization saved to: {args.out}")


if __name__ == "__main__":
    main()
