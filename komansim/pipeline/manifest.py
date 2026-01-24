"""Manifest generation for reproducibility and lineage tracking."""

from __future__ import annotations

import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List
from uuid import uuid4

from komansim.core.backend import SimBackend
from komansim.schemas.job_schema import JobConfig
from komansim.utils.hashing import canonicalize, config_hash, jobspec_hash, dataset_hash


def _get_simdata_version() -> str | None:
    """Get komansim package version if available (tries komansim first, then simdata-platform for compatibility)."""
    try:
        import importlib.metadata

        # Try komansim first
        try:
            return importlib.metadata.version("komansim")
        except Exception:
            # Fallback to simdata-platform for backward compatibility
            return importlib.metadata.version("simdata-platform")
    except Exception:
        try:
            # Fallback for older Python versions
            import pkg_resources

            try:
                return pkg_resources.get_distribution("komansim").version
            except Exception:
                return pkg_resources.get_distribution("simdata-platform").version
        except Exception:
            return None


def _get_git_commit() -> str | None:
    """Get current git commit hash if available."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=Path(__file__).parent.parent.parent,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return None


def _get_backend_name(backend: SimBackend) -> str:
    """Extract backend name from backend instance."""
    # Try to get name from class
    class_name = backend.__class__.__name__
    # Map common class names to backend names
    name_map = {
        "DummyBackend": "dummy",
        "MuJoCoBackend": "mujoco",
        "IsaacSimBackend": "isaac_sim",
    }
    return name_map.get(class_name, class_name.lower().replace("backend", ""))


def _get_backend_version(backend: SimBackend) -> str | None:
    """Get backend version if available."""
    # For now, backends don't expose version info
    # This can be extended later when backends implement version reporting
    return None


def collect_file_inventory(out_dir: Path) -> tuple[List[Dict[str, Any]], Dict[str, int], int, int]:
    """Collect inventory of all files in the output directory.

    Args:
        out_dir: Root output directory to scan

    Returns:
        Tuple of:
        - files: List of file info dicts with 'path' and 'bytes', sorted by path
        - by_suffix_counts: Dict mapping suffix to file count
        - total_files: Total number of files
        - total_bytes: Total size in bytes
    """
    files: List[Dict[str, Any]] = []
    by_suffix_counts: Dict[str, int] = {}
    total_bytes = 0

    if not out_dir.exists():
        return files, by_suffix_counts, 0, 0

    # Walk through all files
    for file_path in sorted(out_dir.rglob("*")):
        if file_path.is_file():
            # Get relative path as POSIX string
            rel_path = file_path.relative_to(out_dir).as_posix()
            file_size = file_path.stat().st_size

            files.append(
                {
                    "path": rel_path,
                    "bytes": file_size,
                }
            )

            # Count by suffix
            suffix = file_path.suffix.lower()
            if suffix:
                by_suffix_counts[suffix] = by_suffix_counts.get(suffix, 0) + 1
            else:
                by_suffix_counts[""] = by_suffix_counts.get("", 0) + 1

            total_bytes += file_size

    # Sort files by path for stable ordering
    files.sort(key=lambda x: x["path"])

    return files, by_suffix_counts, len(files), total_bytes


def build_manifest(
    cfg: JobConfig,
    backend: SimBackend,
    backend_name: str,
    out_dir: Path,
    cache_hit: bool = False,
) -> Dict[str, Any]:
    """Build a manifest dictionary for a completed job run.

    Args:
        cfg: The job configuration
        backend: The backend instance used
        backend_name: Name of the backend (e.g., "dummy", "mujoco")
        out_dir: Output directory path
        cache_hit: Whether this run used a cached dataset

    Returns:
        Manifest dictionary
    """
    # Collect file inventory
    files, by_suffix_counts, total_files, total_bytes = collect_file_inventory(out_dir)

    # Canonicalize config for storage
    config_dict = cfg.model_dump()
    canonical_jobspec = canonicalize(config_dict)

    # Compute hashes
    jobspec_hash_value = jobspec_hash(canonical_jobspec)
    simdata_version = _get_simdata_version()
    dataset_hash_value = dataset_hash(canonical_jobspec, backend_name, simdata_version)

    # Build manifest
    manifest = {
        "schema_version": "manifest.v1",
        "run_id": str(uuid4()),
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "jobspec_hash": jobspec_hash_value,
        "dataset_hash": dataset_hash_value,
        "config_hash": config_hash(config_dict),  # Keep for backwards compatibility
        "cache_hit": cache_hit,
        "jobspec": canonical_jobspec,
        "backend": {
            "name": backend_name,
            "version": _get_backend_version(backend),
        },
        "runtime": {
            "python_version": sys.version.split()[0],
            "platform": platform.platform(),
            "simdata_version": simdata_version,
            "git_commit": _get_git_commit(),
        },
        "output": {
            "out_dir": str(out_dir),
            "total_files": total_files,
            "total_bytes": total_bytes,
            "by_suffix_counts": by_suffix_counts,
        },
        "files": files,
    }

    return manifest


def write_manifest(manifest: Dict[str, Any], out_dir: Path) -> None:
    """Write manifest to manifest.json in the output directory.

    Args:
        manifest: Manifest dictionary
        out_dir: Output directory where manifest.json will be written
    """
    manifest_path = out_dir / "manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
