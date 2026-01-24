"""Dataset packaging.

Creates compressed archives (zip or tar) containing the complete dataset.
"""

from __future__ import annotations

import hashlib
import io
import json
import tarfile
import zipfile
from pathlib import Path
from typing import Literal


def create_package(
    out_dir: Path,
    output_path: Path | None = None,
    format: Literal["zip", "tar"] = "zip",
    include_previews: bool = True,
) -> Path:
    """Create a dataset package containing manifest, annotations, exports, and raw dataset folders.

    Args:
        out_dir: Output directory containing the dataset files
        output_path: Optional output path for the package (default: {out_dir}.{format})
        format: Package format, either "zip" or "tar"
        include_previews: Whether to include previews/ directory if it exists

    Returns:
        Path to the created package file

    Raises:
        ValueError: If format is not "zip" or "tar"
        FileNotFoundError: If required files (manifest.json, annotations.jsonl) don't exist
    """
    if format not in ("zip", "tar"):
        raise ValueError(f"format must be 'zip' or 'tar', got {format}")

    # Check required files exist
    manifest_path = out_dir / "manifest.json"
    annotations_path = out_dir / "annotations.jsonl"

    if not manifest_path.exists():
        raise FileNotFoundError(f"manifest.json not found in {out_dir}")
    if not annotations_path.exists():
        raise FileNotFoundError(f"annotations.jsonl not found in {out_dir}")

    # Determine output path
    if output_path is None:
        output_path = Path(f"{out_dir}.{format}")
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Files/directories to include
    items_to_include = [
        "manifest.json",
        "annotations.jsonl",
        "exports",
        "rgb",  # Always include rgb
    ]

    # Include qa.json if it exists
    qa_path = out_dir / "qa.json"
    if qa_path.exists():
        items_to_include.append("qa.json")

    # Include optional directories if they exist
    for optional_dir in ["depth", "seg", "meta"]:
        if (out_dir / optional_dir).exists() and (out_dir / optional_dir).is_dir():
            items_to_include.append(optional_dir)

    if include_previews:
        previews_dir = out_dir / "previews"
        if previews_dir.exists() and previews_dir.is_dir():
            items_to_include.append("previews")

    # Generate checksums
    checksums = _compute_checksums(out_dir)

    # Generate README
    readme_content = _generate_readme(out_dir)

    # Create package
    if format == "zip":
        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
            _add_to_zip(zf, out_dir, items_to_include)
            # Add checksums.json
            checksums_json = json.dumps(checksums, indent=2, ensure_ascii=False)
            zf.writestr("checksums.json", checksums_json.encode("utf-8"))
            # Add README.txt
            zf.writestr("README.txt", readme_content.encode("utf-8"))
    else:  # tar
        with tarfile.open(output_path, "w:gz") as tf:
            _add_to_tar(tf, out_dir, items_to_include)
            # Add checksums.json
            checksums_data = json.dumps(checksums, indent=2, ensure_ascii=False).encode("utf-8")
            checksums_info = tarfile.TarInfo(name="checksums.json")
            checksums_info.size = len(checksums_data)
            tf.addfile(checksums_info, io.BytesIO(checksums_data))
            # Add README.txt
            readme_data = readme_content.encode("utf-8")
            readme_info = tarfile.TarInfo(name="README.txt")
            readme_info.size = len(readme_data)
            tf.addfile(readme_info, io.BytesIO(readme_data))

    return output_path


def _add_to_zip(zf: zipfile.ZipFile, base_dir: Path, items: list[str]) -> None:
    """Add files and directories to a zip file.

    Args:
        zf: ZipFile object
        base_dir: Base directory containing the items
        items: List of file or directory names to add
    """
    for item_name in items:
        item_path = base_dir / item_name

        if item_path.is_file():
            # Add file with relative path
            zf.write(item_path, item_name)
        elif item_path.is_dir():
            # Add directory recursively
            for file_path in item_path.rglob("*"):
                if file_path.is_file():
                    # Get relative path from base_dir
                    rel_path = file_path.relative_to(base_dir).as_posix()
                    zf.write(file_path, rel_path)


def _add_to_tar(tf: tarfile.TarFile, base_dir: Path, items: list[str]) -> None:
    """Add files and directories to a tar file.

    Args:
        tf: TarFile object
        base_dir: Base directory containing the items
        items: List of file or directory names to add
    """
    for item_name in items:
        item_path = base_dir / item_name

        if item_path.is_file():
            # Add file with relative path
            tf.add(item_path, arcname=item_name)
        elif item_path.is_dir():
            # Add directory recursively
            for file_path in item_path.rglob("*"):
                if file_path.is_file():
                    # Get relative path from base_dir
                    rel_path = file_path.relative_to(base_dir).as_posix()
                    tf.add(file_path, arcname=rel_path)


def _compute_checksums(out_dir: Path) -> dict[str, str]:
    """Compute SHA256 checksums for key files.

    Args:
        out_dir: Output directory containing the dataset files

    Returns:
        Dictionary mapping file paths (relative to out_dir) to SHA256 checksums
    """
    checksums: dict[str, str] = {}

    # Always checksum manifest.json and annotations.jsonl
    for file_name in ["manifest.json", "annotations.jsonl"]:
        file_path = out_dir / file_name
        if file_path.exists():
            checksums[file_name] = _sha256_file(file_path)

    # Checksum all files in exports/
    exports_dir = out_dir / "exports"
    if exports_dir.exists() and exports_dir.is_dir():
        for file_path in sorted(exports_dir.rglob("*")):
            if file_path.is_file():
                rel_path = file_path.relative_to(out_dir).as_posix()
                checksums[rel_path] = _sha256_file(file_path)

    # Checksum rgb files - sample if many, all if small
    rgb_dir = out_dir / "rgb"
    if rgb_dir.exists() and rgb_dir.is_dir():
        rgb_files = sorted(rgb_dir.glob("*.png"))
        # If <= 100 files, checksum all; otherwise sample first 20
        if len(rgb_files) <= 100:
            files_to_checksum = rgb_files
        else:
            files_to_checksum = rgb_files[:20]

        for file_path in files_to_checksum:
            rel_path = file_path.relative_to(out_dir).as_posix()
            checksums[rel_path] = _sha256_file(file_path)

    return checksums


def _sha256_file(file_path: Path) -> str:
    """Compute SHA256 hash of a file.

    Args:
        file_path: Path to the file

    Returns:
        Hexadecimal SHA256 hash string
    """
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def _generate_readme(out_dir: Path) -> str:
    """Generate README.txt content with dataset layout and usage instructions.

    Args:
        out_dir: Output directory containing the dataset files

    Returns:
        README content as string
    """
    # Check what directories exist
    has_depth = (out_dir / "depth").exists()
    has_seg = (out_dir / "seg").exists()
    has_meta = (out_dir / "meta").exists()
    has_previews = (out_dir / "previews").exists()

    readme_lines = [
        "Dataset Package",
        "=" * 50,
        "",
        "Dataset Layout:",
        "  - rgb/              : RGB images (PNG format)",
    ]

    if has_depth:
        readme_lines.append("  - depth/            : Depth maps (NPY format)")
    if has_seg:
        readme_lines.append("  - seg/              : Segmentation masks (NPY format)")
    if has_meta:
        readme_lines.append("  - meta/              : Frame metadata (JSON format)")
    if has_previews:
        readme_lines.append("  - previews/         : Preview images")

    readme_lines.extend(
        [
            "  - manifest.json     : Dataset manifest with metadata and file inventory",
            "  - annotations.jsonl : Canonical annotations (one JSON object per line)",
            "  - exports/          : Exported formats for training",
            "    - coco.json       : COCO format annotations",
            "    - yolo/           : YOLO format label files",
            "  - checksums.json    : SHA256 checksums for key files",
            "",
            "Using COCO Export:",
            "  The exports/coco.json file follows the standard COCO format.",
            "  Each image entry in the 'images' array has a 'file_name' field",
            "  that points to the RGB image in the rgb/ directory.",
            "",
            "  Example usage with Detectron2:",
            "    from detectron2.data.datasets import register_coco_instances",
            "    register_coco_instances(",
            "        'my_dataset',",
            "        {},",
            "        'path/to/dataset/exports/coco.json',",
            "        'path/to/dataset/rgb'",
            "    )",
            "",
            "Using YOLO Export:",
            "  The exports/yolo/ directory contains one .txt file per image.",
            "  Each line in a .txt file represents one object:",
            "    class_id center_x center_y width height",
            "  All coordinates are normalized (0.0 to 1.0).",
            "",
            "  Example usage with YOLOv5/YOLOv8:",
            "    # Place RGB images in a 'images' directory",
            "    # Place YOLO labels in a 'labels' directory",
            "    # Use the standard YOLO dataset structure",
            "",
            "File Naming:",
            "  All frame files use 6-digit zero-padded indices:",
            "    rgb/000000.png, rgb/000001.png, ...",
            "    seg/000000.npy, seg/000001.npy, ...",
            "    meta/000000.json, meta/000001.json, ...",
            "",
            "Checksums:",
            "  The checksums.json file contains SHA256 hashes for:",
            "  - manifest.json",
            "  - annotations.jsonl",
            "  - All files in exports/",
            "  - RGB images (all if <= 100 files, first 20 if more)",
            "",
        ]
    )

    return "\n".join(readme_lines)
