"""Python SDK for KomanSim.

This module provides a simple programmatic API for validating configs,
running jobs, and querying dataset statistics.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Union

from komansim.runtime.run_job import run_job as _run_job
from komansim.runtime.result import RunResult
from komansim.schemas.job_schema import JobConfig


def validate_config(path_or_dict: Union[Path, str, dict]) -> JobConfig:
    """Validate a job configuration file or dictionary.

    Args:
        path_or_dict: Path to YAML config file (str or Path) or config dictionary

    Returns:
        JobConfig object

    Raises:
        FileNotFoundError: If path doesn't exist
        ValueError: If config validation fails

    Example:
        ```python
        from komansim import validate_config

        # From file
        config = validate_config("examples/configs/job_dummy_coco.yaml")

        # From dict
        config = validate_config({"job_name": "test", "num_frames": 10})
        ```
    """
    import yaml

    if isinstance(path_or_dict, (str, Path)):
        path = Path(path_or_dict)
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {path}")
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    elif isinstance(path_or_dict, dict):
        raw = path_or_dict
    else:
        raise TypeError(f"path_or_dict must be Path, str, or dict, got {type(path_or_dict)}")

    return JobConfig.model_validate(raw)


def run(
    path_or_dict: Union[Path, str, JobConfig],
    backend: str,
    cache: bool = True,
    out_dir: Union[Path, str, None] = None,
    seed: int | None = None,
) -> RunResult:
    """Run a synthetic data generation job.

    Args:
        path_or_dict: Path to YAML config file (str or Path), config dict, or JobConfig object
        backend: Backend name (e.g., "dummy", "mujoco", "pybullet", "isaac_sim")
        cache: If True, check registry for cached dataset and skip generation if found
        out_dir: Optional output directory override (overrides config.out_dir)
        seed: Optional seed override (overrides config.seed)

    Returns:
        RunResult object with job execution details

    Raises:
        FileNotFoundError: If config file doesn't exist
        ValueError: If config validation fails
        KeyError: If backend name is not registered
        RuntimeError: If backend initialization fails

    Example:
        ```python
        from komansim import run
        from pathlib import Path

        result = run(
            "examples/configs/job_dummy_coco.yaml",
            backend="dummy",
            cache=True,
            out_dir=Path("outputs/my_job"),
            seed=42
        )

        print(f"Dataset ID: {result.dataset_id}")
        print(f"Package: {result.package_path}")
        print(f"Cache hit: {result.cache_hit}")
        ```
    """
    # Load config if needed
    if isinstance(path_or_dict, (str, Path)):
        config_obj = validate_config(path_or_dict)
    elif isinstance(path_or_dict, dict):
        config_obj = validate_config(path_or_dict)
    elif isinstance(path_or_dict, JobConfig):
        config_obj = path_or_dict
    else:
        raise TypeError(
            f"path_or_dict must be Path, str, dict, or JobConfig, got {type(path_or_dict)}"
        )

    # Convert out_dir to Path if provided as str
    out_dir_path = Path(out_dir) if isinstance(out_dir, str) else out_dir

    return _run_job(
        config_path_or_obj=config_obj,
        backend=backend,
        out_dir=out_dir_path,
        seed=seed,
        use_cache=cache,
        raise_on_failure=False,  # Return RunResult instead of raising
    )


def stats(out_dir: Union[Path, str]) -> dict:
    """Get statistics and metadata from a generated dataset.

    Args:
        out_dir: Path to the output directory (str or Path)

    Returns:
        Dictionary with statistics including:
        - num_frames: Number of frames generated
        - dataset_hash: Dataset hash from manifest
        - jobspec_hash: Jobspec hash from manifest
        - backend: Backend name used
        - total_files: Total number of files
        - total_bytes: Total size in bytes
        - cache_hit: Whether this was a cache hit

    Raises:
        FileNotFoundError: If out_dir doesn't exist or manifest.json is missing

    Example:
        ```python
        from komansim import stats
        from pathlib import Path

        stats_dict = stats(Path("outputs/my_job"))
        print(f"Frames: {stats_dict['num_frames']}")
        print(f"Dataset Hash: {stats_dict['dataset_hash']}")
        ```
    """
    out_path = Path(out_dir)
    if not out_path.exists():
        raise FileNotFoundError(f"Output directory not found: {out_path}")

    manifest_path = out_path / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest not found: {manifest_path}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    # Extract key statistics
    stats_dict = {
        "dataset_hash": manifest.get("dataset_hash", ""),
        "jobspec_hash": manifest.get("jobspec_hash", ""),
        "backend": manifest.get("backend", {}).get("name", "unknown"),
        "total_files": manifest.get("output", {}).get("total_files", 0),
        "total_bytes": manifest.get("output", {}).get("total_bytes", 0),
        "cache_hit": manifest.get("cache_hit", False),
    }

    # Count frames from RGB directory or metadata
    rgb_dir = out_path / "rgb"
    if rgb_dir.exists():
        rgb_files = list(rgb_dir.glob("*.png"))
        stats_dict["num_frames"] = len(rgb_files)
    else:
        # Fallback: count metadata files
        meta_dir = out_path / "meta"
        if meta_dir.exists():
            meta_files = list(meta_dir.glob("*.json"))
            stats_dict["num_frames"] = len(meta_files)
        else:
            stats_dict["num_frames"] = 0

    return stats_dict
