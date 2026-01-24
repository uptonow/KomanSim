"""Result objects for job execution.

This module provides structured result objects for job execution that can be
used by both programmatic API and server/worker implementations.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel


class RunResult(BaseModel):
    """Structured result from running a job.

    This object is returned by run_job() to provide consistent information
    about the job execution, including cache hits, generation results, and errors.

    Attributes:
        job_id: Optional job identifier (reserved for future use)
        dataset_id: Unique identifier for the dataset
        config_hash: SHA256 hash of the canonicalized config
        backend: Backend name used (e.g., "dummy", "mujoco")
        out_dir: Output directory path
        package_path: Path to the packaged dataset (zip/tar file)
        manifest_path: Path to the manifest.json file
        status: Job status - "succeeded" or "failed"
        cache_hit: Whether this result came from cache (True) or fresh generation (False)
        error: Error message if status is "failed", None otherwise
    """

    job_id: Optional[str] = None
    dataset_id: str
    config_hash: str
    backend: str
    out_dir: str
    package_path: str
    manifest_path: str
    status: Literal["succeeded", "failed"]
    cache_hit: bool
    error: Optional[str] = None
