"""Runtime function for executing synthetic data generation jobs.

This module provides a high-level interface for running jobs that can be
imported and used programmatically, not just from the CLI.
"""

from __future__ import annotations

from pathlib import Path
from typing import Union

import yaml

from komansim.core.backend import SimBackend
from komansim.core.registry import make_backend
from komansim.pipeline.generate import JobFailedError, run_job as _run_job
from komansim.runtime.result import RunResult
from komansim.schemas.job_schema import JobConfig


def _ensure_backends_registered() -> None:
    """Ensure all backends are registered (idempotent)."""
    import komansim.backends.dummy.backend  # noqa: F401
    import komansim.backends.isaac_sim.backend  # noqa: F401
    import komansim.backends.mujoco.backend  # noqa: F401
    import komansim.backends.pybullet.backend  # noqa: F401


def _load_config(path: Path) -> JobConfig:
    """Load and validate a job config from a YAML file."""
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return JobConfig.model_validate(raw)


def run_job(
    config_path_or_obj: Union[Path, JobConfig],
    backend: Union[str, SimBackend],
    out_dir: Union[str, Path, None] = None,
    seed: int | None = None,
    job_id: str | None = None,
    use_cache: bool = False,
    raise_on_failure: bool = True,
) -> RunResult:
    """Run a synthetic data generation job.

    This is the main entry point for programmatic job execution. It handles
    config loading, backend creation, and job execution.

    Args:
        config_path_or_obj: Path to YAML config file or JobConfig object
        backend: Backend name (str) or SimBackend instance
        out_dir: Optional output directory override (overrides config.out_dir)
        seed: Optional seed override (overrides config.seed)
        job_id: Optional job ID (currently unused, reserved for future use)
        use_cache: If True, check registry for cached dataset and skip generation if found
        raise_on_failure: If True, raise JobFailedError on failure. If False, return RunResult with status="failed"

    Returns:
        RunResult object with job execution details

    Raises:
        FileNotFoundError: If config_path is a Path that doesn't exist
        ValueError: If config validation fails
        KeyError: If backend name is not registered
        RuntimeError: If backend initialization fails
        JobFailedError: If job fails and raise_on_failure=True

    Example:
        ```python
        from komansim.runtime.run_job import run_job
        from pathlib import Path

        # Using config file path
        result = run_job(
            config_path_or_obj=Path("examples/configs/job.yaml"),
            backend="dummy",
            out_dir="outputs/my_job",
            seed=42
        )
        print(f"Dataset ID: {result.dataset_id}, Cache hit: {result.cache_hit}")

        # Using JobConfig object
        from komansim.schemas.job_schema import JobConfig
        config = JobConfig(job_name="test", num_frames=10, dt=0.1)
        result = run_job(config_path_or_obj=config, backend="dummy")
        ```
    """
    # Load config if needed
    if isinstance(config_path_or_obj, Path):
        cfg = _load_config(config_path_or_obj)
    elif isinstance(config_path_or_obj, JobConfig):
        cfg = config_path_or_obj
    else:
        raise TypeError(
            f"config_path_or_obj must be Path or JobConfig, got {type(config_path_or_obj)}"
        )

    # Override config values if provided
    if out_dir is not None:
        cfg = cfg.model_copy(update={"out_dir": str(out_dir)})
    if seed is not None:
        cfg = cfg.model_copy(update={"seed": seed})
    if job_id is not None:
        # Store job_id in config for future use (e.g., metadata)
        # For now, we'll add it to job_name or keep it for metadata
        pass  # Reserved for future use

    # Determine backend name for hashing and result
    backend_name_for_hash = cfg.backend if cfg.backend else None
    if backend_name_for_hash is None:
        if isinstance(backend, str):
            backend_name_for_hash = backend
        else:
            # Backend instance - infer name from class
            from komansim.pipeline.manifest import _get_backend_name

            backend_name_for_hash = _get_backend_name(backend)

    # Compute hashes
    from komansim.registry.local_registry import LocalRegistry
    from komansim.utils.hashing import canonicalize, dataset_hash
    from komansim.pipeline.manifest import _get_simdata_version

    registry = LocalRegistry()
    config_dict = cfg.model_dump()
    canonical_jobspec = canonicalize(config_dict)
    simdata_version = _get_simdata_version()

    # Compute dataset_hash (cache_key) for cache lookup
    dataset_hash_value = dataset_hash(canonical_jobspec, backend_name_for_hash, simdata_version)

    # Check cache if use_cache is enabled
    if use_cache:
        entry = registry.find_by_dataset_hash_with_validation(dataset_hash_value)

        if entry:
            # Verify backend matches - raise error if mismatch
            if entry.get("backend") != backend_name_for_hash:
                raise ValueError(
                    f"Backend mismatch in cache: Registry entry has backend '{entry.get('backend')}' "
                    f"but config requires '{backend_name_for_hash}'. Cache entry is invalid for this backend."
                )

            # Cache hit - return RunResult without running generation
            out_dir_path = Path(entry["out_dir"])
            package_path = Path(entry["package_path"])
            manifest_path = out_dir_path / "manifest.json"

            return RunResult(
                job_id=job_id,
                dataset_id=entry["dataset_id"],
                config_hash=entry.get("config_hash", dataset_hash_value),  # Backwards compatibility
                backend=entry["backend"],
                out_dir=str(out_dir_path),
                package_path=str(package_path),
                manifest_path=str(manifest_path),
                status="succeeded",
                cache_hit=True,
                error=None,
            )

    # Ensure backends are registered
    _ensure_backends_registered()

    # Create or use backend
    backend_name: str | None = None
    if isinstance(backend, str):
        backend_name = backend
        be = make_backend(
            backend,
            headless=cfg.headless,
            width=cfg.width,
            height=cfg.height,
        )
    elif isinstance(backend, SimBackend):
        be = backend
        # Backend name will be inferred in pipeline
    else:
        raise TypeError(f"backend must be str or SimBackend, got {type(backend)}")

    # Run the job using the existing pipeline function
    out_dir_path = Path(cfg.out_dir)
    try:
        _run_job(be, cfg, backend_name=backend_name, use_cache=use_cache)

        # After successful generation, look up the registry entry to get dataset_id
        # The pipeline function registers the dataset, so we can find it by dataset_hash
        # Create a new registry instance to ensure we're using the correct home directory
        # (important for tests that mock Path.home())
        registry = LocalRegistry()
        entry = registry.find_by_dataset_hash(dataset_hash_value)
        if not entry:
            # This shouldn't happen, but handle gracefully
            raise RuntimeError("Job completed but dataset was not registered in registry")

        # Find package path (could be .zip or .tar)
        package_path = None
        if entry.get("package_path"):
            package_path = Path(entry["package_path"])
        else:
            # Fallback: try to find package by convention
            for ext in [".zip", ".tar"]:
                potential_package = Path(f"{out_dir_path}{ext}")
                if potential_package.exists():
                    package_path = potential_package
                    break

        if not package_path or not package_path.exists():
            raise RuntimeError(f"Package file not found for dataset {entry['dataset_id']}")

        manifest_path = out_dir_path / "manifest.json"

        return RunResult(
            job_id=job_id,
            dataset_id=entry["dataset_id"],
            config_hash=entry.get("config_hash", dataset_hash_value),  # Backwards compatibility
            backend=entry["backend"],
            out_dir=str(out_dir_path),
            package_path=str(package_path),
            manifest_path=str(manifest_path),
            status="succeeded",
            cache_hit=False,
            error=None,
        )
    except JobFailedError as e:
        # Look up registry entry if it exists (might have been created before failure)
        # Create a new registry instance to ensure we're using the correct home directory
        registry = LocalRegistry()
        entry = registry.find_by_dataset_hash(dataset_hash_value)
        dataset_id = entry["dataset_id"] if entry else "unknown"

        # Try to find package and manifest paths
        package_path = None
        if entry and entry.get("package_path"):
            package_path = Path(entry["package_path"])
        else:
            # Try convention-based lookup
            for ext in [".zip", ".tar"]:
                potential_package = Path(f"{out_dir_path}{ext}")
                if potential_package.exists():
                    package_path = potential_package
                    break

        manifest_path = out_dir_path / "manifest.json"

        result = RunResult(
            job_id=job_id,
            dataset_id=dataset_id,
            config_hash=entry.get("config_hash", dataset_hash_value)
            if entry
            else dataset_hash_value,
            backend=backend_name_for_hash or "unknown",
            out_dir=str(out_dir_path),
            package_path=str(package_path) if package_path and package_path.exists() else "",
            manifest_path=str(manifest_path) if manifest_path.exists() else "",
            status="failed",
            cache_hit=False,
            error=str(e),
        )

        if raise_on_failure:
            raise e
        return result
    except Exception as e:
        # Handle other exceptions similarly
        # Create a new registry instance to ensure we're using the correct home directory
        registry = LocalRegistry()
        entry = registry.find_by_dataset_hash(dataset_hash_value)
        dataset_id = entry["dataset_id"] if entry else "unknown"

        package_path = None
        if entry and entry.get("package_path"):
            package_path = Path(entry["package_path"])

        manifest_path = out_dir_path / "manifest.json"

        result = RunResult(
            job_id=job_id,
            dataset_id=dataset_id,
            config_hash=entry.get("config_hash", dataset_hash_value)
            if entry
            else dataset_hash_value,
            backend=backend_name_for_hash or "unknown",
            out_dir=str(out_dir_path),
            package_path=str(package_path) if package_path and package_path.exists() else "",
            manifest_path=str(manifest_path) if manifest_path.exists() else "",
            status="failed",
            cache_hit=False,
            error=str(e),
        )

        if raise_on_failure:
            # Wrap in JobFailedError for consistency
            raise JobFailedError(str(e)) from e
        return result
