from __future__ import annotations

import math
import random
from pathlib import Path

from komansim.core.backend import SimBackend
from komansim.core.types import AssetSpec, Pose, SceneSpec, SensorSpec
from komansim.pipeline.annotations import generate_annotations, write_annotations
from komansim.pipeline.exporters.coco import export_coco
from komansim.pipeline.exporters.yolo import export_yolo
from komansim.pipeline.manifest import build_manifest, write_manifest
from komansim.pipeline.package import create_package
from komansim.pipeline.writers import write_sample
from komansim.schemas.job_schema import JobConfig


class JobFailedError(Exception):
    """Exception raised when a job fails due to resource limits or other errors."""

    pass


def _rand_pose(base: Pose, random_xy: float, random_yaw_deg: float, rng: random.Random) -> Pose:
    dx = (rng.random() * 2 - 1) * random_xy
    dy = (rng.random() * 2 - 1) * random_xy
    yaw = math.radians((rng.random() * 2 - 1) * random_yaw_deg)
    q = (0.0, 0.0, math.sin(yaw / 2.0), math.cos(yaw / 2.0))  # xyzw (yaw around z)
    return Pose(p=(base.p[0] + dx, base.p[1] + dy, base.p[2]), q=q)


def _get_directory_size(out_dir: Path) -> int:
    """Calculate total size of all files in a directory.

    Args:
        out_dir: Directory to calculate size for

    Returns:
        Total size in bytes
    """
    total_size = 0
    if not out_dir.exists():
        return 0

    for file_path in out_dir.rglob("*"):
        if file_path.is_file():
            try:
                total_size += file_path.stat().st_size
            except (OSError, FileNotFoundError):
                # Skip files that can't be accessed
                pass

    return total_size


def _write_failed_manifest(
    cfg: JobConfig,
    backend_name: str,
    out_dir: Path,
    error_message: str,
    frames_completed: int,
) -> None:
    """Write a failed manifest with error information.

    Args:
        cfg: The job configuration
        backend_name: Name of the backend
        out_dir: Output directory path
        error_message: Error message describing the failure
        frames_completed: Number of frames completed before failure
    """
    from datetime import datetime, timezone
    from uuid import uuid4

    failed_manifest = {
        "schema_version": "manifest.v1",
        "run_id": str(uuid4()),
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "failed",
        "error": error_message,
        "frames_completed": frames_completed,
        "frames_requested": cfg.num_frames,
        "jobspec": cfg.model_dump(),
        "backend": {
            "name": backend_name,
        },
        "output": {
            "out_dir": str(out_dir),
        },
    }

    manifest_path = out_dir / "manifest.json"
    import json

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(failed_manifest, f, indent=2, ensure_ascii=False)


def run_job(
    backend: SimBackend, cfg: JobConfig, backend_name: str | None = None, use_cache: bool = False
) -> None:
    out_dir = Path(cfg.out_dir)
    rng = random.Random(cfg.seed)

    backend.start()
    backend.reset(seed=cfg.seed)

    scene = SceneSpec(**cfg.scene.model_dump())
    backend.load_scene(scene)

    # sensors
    for s in cfg.sensors:
        pose = Pose(p=tuple(s.pose.p), q=tuple(s.pose.q))  # type: ignore[arg-type]
        backend.add_sensor(SensorSpec(name=s.name, type=s.type, pose=pose, intrinsics=s.intrinsics))

    # assets
    handles = []
    # Spawn each asset at a different initial position to avoid overlap
    # Offset by index to ensure separation while keeping objects in camera view
    for idx, a in enumerate(cfg.assets):
        spec = AssetSpec(**a.model_dump())
        # Offset each object to ensure clear separation (0.5m spacing)
        # Place objects in a line along x-axis, centered around origin
        # For 2 objects: -0.25m and +0.25m (0.5m apart)
        # For 3+ objects: evenly spaced
        num_assets = len(cfg.assets)
        # Use 0.3m spacing - enough to avoid overlap but keep objects in view
        # For 2 objects: -0.15m and +0.15m (0.3m apart)
        spacing = 0.3
        offset_x = (idx - (num_assets - 1) / 2) * spacing
        offset_y = 0.0  # Keep on same y-axis for better visibility
        # z=0.15 to ensure objects are above the floor plane (which is at z=0)
        base_pose = Pose((offset_x, offset_y, 0.15), (0.0, 0.0, 0.0, 1.0))
        h = backend.spawn_asset(spec, base_pose)
        handles.append((h, base_pose))

    # loop - collect seg arrays and meta for annotations
    seg_arrays = []
    meta_list = []

    try:
        for i in range(cfg.num_frames):
            for h, base in handles:
                rp = cfg.randomization
                backend.set_pose(h, _rand_pose(base, rp.random_xy, rp.random_yaw_deg, rng))

            backend.step(cfg.dt)
            frames = backend.render()
            meta = frames.meta or {}
            meta.update({"job_name": cfg.job_name, "frame_index": i})

            write_sample(out_dir, i, frames.rgb, frames.depth, frames.seg, meta)

            # Collect seg and meta for annotations generation
            seg_arrays.append(frames.seg)
            meta_list.append(meta)

            # Periodic disk usage check (every 10 frames)
            if cfg.max_total_size is not None and (i + 1) % 10 == 0:
                current_size = _get_directory_size(out_dir)
                if current_size > cfg.max_total_size:
                    error_msg = (
                        f"Disk usage limit exceeded: {current_size:,} bytes "
                        f"(limit: {cfg.max_total_size:,} bytes) at frame {i + 1}/{cfg.num_frames}"
                    )
                    if backend_name is None:
                        from komansim.pipeline.manifest import _get_backend_name

                        backend_name = _get_backend_name(backend)
                    _write_failed_manifest(cfg, backend_name, out_dir, error_msg, i + 1)
                    backend.close()
                    raise JobFailedError(error_msg)

        backend.close()

        # Generate and write annotations.jsonl
        annotations = generate_annotations(
            out_dir=out_dir,
            num_frames=cfg.num_frames,
            seg_arrays=seg_arrays,
            meta_list=meta_list,
            min_bbox_area=1,
            validate_integrity_checks=True,
        )
        write_annotations(annotations, out_dir, validate=True)

        # Export to standard formats (COCO, YOLO)
        annotations_path = out_dir / "annotations.jsonl"
        export_coco(annotations_path, out_dir)
        export_yolo(annotations_path, out_dir)

        # Generate previews and QA
        from komansim.pipeline.qa import generate_previews, generate_qa

        previews_dir = generate_previews(out_dir, num_previews=8, max_size=512)
        qa_path = out_dir / "qa.json"
        generate_qa(
            annotations_path, qa_path, previews_dir=previews_dir if previews_dir.exists() else None
        )

        # Write manifest after successful job completion (includes exports in inventory)
        if backend_name is None:
            # Infer backend name from class
            from komansim.pipeline.manifest import _get_backend_name

            backend_name = _get_backend_name(backend)

        # cache_hit is always False here since we only reach this point if cache was not hit
        manifest = build_manifest(cfg, backend, backend_name, out_dir, cache_hit=False)
        write_manifest(manifest, out_dir)

        # Create dataset package (after manifest is written)
        package_path = create_package(out_dir, format="zip")

        # Register dataset in registry
        if backend_name is None:
            from komansim.pipeline.manifest import _get_backend_name

            backend_name = _get_backend_name(backend)

        from komansim.registry.local_registry import LocalRegistry
        from komansim.utils.hashing import canonicalize, jobspec_hash, dataset_hash
        from komansim.pipeline.manifest import _get_simdata_version

        registry = LocalRegistry()
        config_dict = cfg.model_dump()
        canonical_jobspec = canonicalize(config_dict)
        simdata_version = _get_simdata_version()

        # Compute hashes
        jobspec_hash_value = jobspec_hash(canonical_jobspec)
        dataset_hash_value = dataset_hash(canonical_jobspec, backend_name, simdata_version)

        # For backwards compatibility, also compute old config_hash
        from komansim.utils.hashing import config_hash

        old_config_hash = config_hash(
            {**config_dict, "_backend": backend_name if backend_name else "unknown"}
        )

        registry.register(
            dataset_hash=dataset_hash_value,
            jobspec_hash=jobspec_hash_value,
            config_hash=old_config_hash,  # Keep for backwards compatibility
            backend=backend_name,
            out_dir=out_dir,
            package_path=package_path,
            template=None,  # TODO: extract from config when templates are implemented
        )
    except JobFailedError:
        # Re-raise JobFailedError as-is
        raise
    except Exception as e:
        # Wrap other exceptions in JobFailedError
        error_msg = f"Job failed with error: {str(e)}"
        if backend_name is None:
            from komansim.pipeline.manifest import _get_backend_name

            backend_name = _get_backend_name(backend)
        _write_failed_manifest(cfg, backend_name, out_dir, error_msg, len(seg_arrays))
        # Only close backend if it hasn't been closed yet
        try:
            backend.close()
        except Exception:
            pass  # Backend may already be closed
        raise JobFailedError(error_msg) from e
