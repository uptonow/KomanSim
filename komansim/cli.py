from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path
from typing import Optional

import typer
import yaml

from komansim.runtime.run_job import run_job

# Check if called via deprecated 'simdata' command
if len(sys.argv) > 0 and "simdata" in sys.argv[0]:
    warnings.warn(
        "The 'simdata' CLI command is deprecated and will be removed in a future version. "
        "Please use 'komansim' instead. Example: 'komansim run --backend dummy --config <path>'",
        DeprecationWarning,
        stacklevel=1,
    )

app = typer.Typer(add_completion=False, no_args_is_help=True)
datasets_app = typer.Typer(help="Manage local dataset registry.")
app.add_typer(datasets_app, name="datasets")


@app.command()
def init(path: Path = typer.Argument(..., help="Where to write a starter YAML config.")):
    """Create a starter config file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise typer.BadParameter(f"File already exists: {path}")
    starter = {
        "job_name": "demo_job",
        "out_dir": "outputs/demo_job",
        "seed": 0,
        "num_frames": 20,
        "dt": 1.0 / 30.0,
        "headless": True,
        "width": 640,
        "height": 480,
        "scene": {"usd_path": None, "physics_dt": 1.0 / 60.0, "dome_light_intensity": 1500.0},
        "assets": [
            {
                "name": "obj_01",
                "usd_path": "PATH/TO/YOUR_ASSET.usd",
                "semantic_label": "object",
                "scale": 1.0,
            }
        ],
        "sensors": [
            {
                "name": "cam0",
                "type": "camera_rgb",
                "pose": {"p": [1.5, 1.5, 1.2], "q": [0.0, 0.0, 0.0, 1.0]},
                "intrinsics": {"fx": 500, "fy": 500, "cx": 320, "cy": 240},
            }
        ],
        "randomization": {"random_xy": 0.2, "random_yaw_deg": 180.0},
    }
    path.write_text(yaml.safe_dump(starter, sort_keys=False), encoding="utf-8")
    typer.echo(f"Wrote starter config -> {path}")


@app.command()
def validate(config: Path = typer.Argument(..., help="Path to YAML job config.")):
    """Validate a job config."""
    from komansim.schemas.job_schema import JobConfig
    import yaml

    raw = yaml.safe_load(config.read_text(encoding="utf-8"))
    cfg = JobConfig.model_validate(raw)
    typer.echo("Config is valid.")
    typer.echo(json.dumps(cfg.model_dump(), indent=2, ensure_ascii=False))


@app.command()
def run(
    config: Path = typer.Option(..., "--config", "-c", help="Path to YAML job config."),
    backend: str = typer.Option(
        "dummy", "--backend", help="Backend name: dummy | isaac_sim | mujoco | pybullet"
    ),
    headless: Optional[bool] = typer.Option(None, "--headless", help="Override config headless."),
    cache: bool = typer.Option(False, "--cache", help="Use cached dataset if available."),
):
    """Run a synthetic-data generation job."""
    from komansim.schemas.job_schema import JobConfig
    import yaml

    # Load config to check headless override
    raw = yaml.safe_load(config.read_text(encoding="utf-8"))
    cfg = JobConfig.model_validate(raw)

    # Validate backend: if specified in config, it must match --backend flag
    if cfg.backend is not None:
        if cfg.backend != backend:
            raise typer.BadParameter(
                f"Backend mismatch: Config specifies '{cfg.backend}' but --backend flag is '{backend}'. "
                f"They must match. Either remove 'backend' from config or use --backend {cfg.backend}"
            )
    else:
        # If backend not in config, use the one from CLI flag and set it in config
        cfg = cfg.model_copy(update={"backend": backend})

    # Validate asset format compatibility with backend (strict validation)
    backend_to_use = cfg.backend
    for asset in cfg.assets:
        usd_path = asset.usd_path
        if usd_path:
            # Check if asset format is compatible with backend
            # Note: We validate all paths, including placeholders, to ensure backend compatibility
            is_placeholder = usd_path == "PATH/TO/YOUR_ASSET.usd"

            if backend_to_use == "pybullet":
                if not usd_path.startswith("primitive://"):
                    placeholder_msg = " (placeholder path)" if is_placeholder else ""
                    raise typer.BadParameter(
                        f"Asset format mismatch: Asset '{asset.name}' has usd_path='{usd_path}'{placeholder_msg} but PyBullet backend only supports primitive:// assets.\n"
                        f"  Supported formats: primitive://box, primitive://sphere\n"
                        f"  Either:\n"
                        f"    1. Change usd_path to a primitive:// asset (e.g., primitive://box)\n"
                        f"    2. Use a different backend that supports this asset format (e.g., isaac_sim for USD files, dummy for placeholders)"
                    )
            elif backend_to_use == "mujoco":
                if not usd_path.endswith((".mjcf", ".xml")):
                    placeholder_msg = " (placeholder path)" if is_placeholder else ""
                    raise typer.BadParameter(
                        f"Asset format mismatch: Asset '{asset.name}' has usd_path='{usd_path}'{placeholder_msg} but MuJoCo backend expects MJCF XML files.\n"
                        f"  Supported formats: .mjcf, .xml\n"
                        f"  Either:\n"
                        f"    1. Change usd_path to an MJCF file (e.g., assets/my_object.mjcf)\n"
                        f"    2. Use a different backend that supports this asset format (e.g., isaac_sim for USD files, dummy for placeholders)"
                    )
            elif backend_to_use == "isaac_sim":
                if not usd_path.endswith((".usd", ".usda", ".usdc")):
                    placeholder_msg = " (placeholder path)" if is_placeholder else ""
                    raise typer.BadParameter(
                        f"Asset format mismatch: Asset '{asset.name}' has usd_path='{usd_path}'{placeholder_msg} but Isaac Sim backend expects USD files.\n"
                        f"  Supported formats: .usd, .usda, .usdc\n"
                        f"  Either:\n"
                        f"    1. Change usd_path to a USD file (e.g., assets/my_object.usd)\n"
                        f"    2. Use a different backend that supports this asset format (e.g., dummy for placeholders)"
                    )

    # Apply headless override if provided
    if headless is not None:
        cfg = cfg.model_copy(update={"headless": headless})

    # Use the runtime run_job function
    # Use backend from config (which now always has it set)
    result = run_job(
        config_path_or_obj=cfg,
        backend=cfg.backend,
        use_cache=cache,
    )

    # Print result based on cache hit status
    if result.cache_hit:
        typer.echo("CACHE HIT")
        typer.echo(f"Dataset ID: {result.dataset_id}")
        typer.echo(f"Package: {result.package_path}")
    else:
        typer.echo("GENERATED")
        typer.echo(f"Dataset ID: {result.dataset_id}")
        typer.echo(f"Package: {result.package_path}")

    # Show hashes from manifest if available
    manifest_path = Path(result.out_dir) / "manifest.json"
    if manifest_path.exists():
        import json

        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if "dataset_hash" in manifest:
                typer.echo(f"Dataset Hash: {manifest['dataset_hash'][:16]}...")
            if "jobspec_hash" in manifest:
                typer.echo(f"Jobspec Hash: {manifest['jobspec_hash'][:16]}...")
        except Exception:
            pass  # Ignore errors reading manifest

    # If job failed, exit with error code
    if result.status == "failed":
        typer.echo(f"Error: {result.error}", err=True)
        raise typer.Exit(1)


@datasets_app.command("list")
def datasets_list(
    show_orphaned: bool = typer.Option(
        False, "--show-orphaned", help="Mark orphaned entries (missing package files)."
    ),
):
    """List all datasets in the local registry."""
    from komansim.registry.local_registry import LocalRegistry

    registry = LocalRegistry()
    entries = registry.list_all()

    if not entries:
        typer.echo("No datasets found in registry.")
        return

    typer.echo(f"Found {len(entries)} dataset(s):\n")
    for entry in entries:
        orphaned = False
        package_path = entry.get("package_path")
        if package_path and show_orphaned:
            orphaned = not Path(package_path).exists()

        typer.echo(f"Dataset ID: {entry['dataset_id']}")
        typer.echo(f"  Created: {entry['created_at']}")
        typer.echo(f"  Backend: {entry['backend']}")
        if "dataset_hash" in entry:
            typer.echo(f"  Dataset Hash: {entry['dataset_hash'][:16]}...")
        if "jobspec_hash" in entry:
            typer.echo(f"  Jobspec Hash: {entry['jobspec_hash'][:16]}...")
        if "config_hash" in entry:
            typer.echo(f"  Config Hash (legacy): {entry['config_hash'][:16]}...")
        typer.echo(f"  Output Dir: {entry['out_dir']}")
        if package_path:
            status = " ⚠️  ORPHANED" if orphaned else ""
            typer.echo(f"  Package: {package_path}{status}")
        if entry.get("template"):
            typer.echo(f"  Template: {entry['template']}")
        typer.echo()


@datasets_app.command("show")
def datasets_show(dataset_id: str = typer.Argument(..., help="Dataset ID to show.")):
    """Show details for a specific dataset."""
    from komansim.registry.local_registry import LocalRegistry

    registry = LocalRegistry()
    entry = registry.find_by_dataset_id(dataset_id)

    if not entry:
        typer.echo(f"Dataset not found: {dataset_id}", err=True)
        raise typer.Exit(1)

    # Check if package exists
    package_path = entry.get("package_path")
    if package_path:
        if not Path(package_path).exists():
            typer.echo(f"⚠️  Warning: Package file is missing: {package_path}", err=True)
            typer.echo(
                "This is an orphaned registry entry. Run 'simdata datasets cleanup' to remove it.",
                err=True,
            )
            typer.echo()

    typer.echo(json.dumps(entry, indent=2, ensure_ascii=False))


@datasets_app.command("cleanup")
def datasets_cleanup(
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Show what would be removed without actually removing."
    ),
    duplicates: bool = typer.Option(
        False, "--duplicates", help="Also remove duplicate entries with same config_hash."
    ),
):
    """Remove orphaned registry entries (where package files don't exist)."""
    from komansim.registry.local_registry import LocalRegistry

    registry = LocalRegistry()

    if dry_run:
        # Count orphaned entries
        orphaned = []
        for entry in registry.list_all():
            package_path = entry.get("package_path")
            if package_path and not Path(package_path).exists():
                orphaned.append(entry)

        if orphaned:
            typer.echo(f"Would remove {len(orphaned)} orphaned dataset(s):")
            for entry in orphaned:
                typer.echo(f"  - {entry['dataset_id']}: {entry.get('package_path', 'N/A')}")
        else:
            typer.echo("No orphaned entries found.")

        # Count duplicates if requested
        if duplicates:
            from collections import defaultdict

            by_hash = defaultdict(list)
            for entry in registry.list_all():
                config_hash = entry.get("config_hash")
                if config_hash:
                    by_hash[config_hash].append(entry)

            duplicate_groups = {h: entries for h, entries in by_hash.items() if len(entries) > 1}
            if duplicate_groups:
                total_duplicates = sum(len(entries) - 1 for entries in duplicate_groups.values())
                typer.echo(
                    f"\nWould remove {total_duplicates} duplicate dataset(s) (keeping newest for each config_hash):"
                )
                for config_hash, entries in duplicate_groups.items():
                    typer.echo(
                        f"  Config hash {config_hash[:16]}...: {len(entries)} entries (would keep 1, remove {len(entries) - 1})"
                    )
            else:
                typer.echo("\nNo duplicate entries found.")
    else:
        removed_orphaned = registry.cleanup_orphaned()
        removed_duplicates = 0
        if duplicates:
            removed_duplicates = registry.cleanup_duplicates(keep_newest=True)

        total_removed = removed_orphaned + removed_duplicates
        if total_removed > 0:
            parts = []
            if removed_orphaned > 0:
                parts.append(f"{removed_orphaned} orphaned")
            if removed_duplicates > 0:
                parts.append(f"{removed_duplicates} duplicate")
            typer.echo(f"Removed {total_removed} dataset entry/entries ({', '.join(parts)}).")
        else:
            typer.echo("No orphaned or duplicate entries found.")


@datasets_app.command("clear")
def datasets_clear(
    confirm: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt."),
    remove_files: bool = typer.Option(
        False, "--remove-files", help="Also remove dataset files (output directories and packages)."
    ),
):
    """Clear all entries from the registry.

    By default, only clears registry entries. Use --remove-files to also delete
    the actual dataset files (output directories and package files).
    """
    from komansim.registry.local_registry import LocalRegistry
    import shutil

    registry = LocalRegistry()
    entries = registry.list_all()
    count = len(entries)

    if count == 0:
        typer.echo("Registry is already empty.")
        return

    # Build confirmation message
    if remove_files:
        # Count files that would be deleted
        dirs_to_remove = set()
        files_to_remove = []
        for entry in entries:
            out_dir = entry.get("out_dir")
            package_path = entry.get("package_path")
            if out_dir:
                dirs_to_remove.add(out_dir)
            if package_path:
                files_to_remove.append(package_path)

        if not confirm:
            typer.echo("⚠️  WARNING: This will:")
            typer.echo(f"   - Remove {count} registry entry/entries")
            typer.echo(f"   - Delete {len(dirs_to_remove)} output directory/directories")
            typer.echo(f"   - Delete {len(files_to_remove)} package file/files")
            typer.echo()
            typer.echo("This action cannot be undone!")
            typer.confirm(
                "Are you sure you want to clear registry AND delete all dataset files?", abort=True
            )
    else:
        if not confirm:
            typer.echo(f"This will remove {count} registry entry/entries.")
            typer.echo(
                "Note: Dataset files will NOT be deleted. Use --remove-files to also delete files."
            )
            typer.confirm("Are you sure you want to clear all registry entries?", abort=True)

    # Remove files if requested
    if remove_files:
        removed_dirs = 0
        removed_files = 0

        for entry in entries:
            # Remove output directory
            out_dir = entry.get("out_dir")
            if out_dir:
                out_path = Path(out_dir)
                if out_path.exists() and out_path.is_dir():
                    try:
                        shutil.rmtree(out_path)
                        removed_dirs += 1
                    except Exception as e:
                        typer.echo(f"Warning: Could not remove directory {out_dir}: {e}", err=True)

            # Remove package file
            package_path = entry.get("package_path")
            if package_path:
                pkg_path = Path(package_path)
                if pkg_path.exists() and pkg_path.is_file():
                    try:
                        pkg_path.unlink()
                        removed_files += 1
                    except Exception as e:
                        typer.echo(f"Warning: Could not remove file {package_path}: {e}", err=True)

        typer.echo(
            f"Removed {removed_dirs} output directory/directories and {removed_files} package file/files."
        )

    # Clear registry
    registry.clear()
    typer.echo(f"Cleared {count} dataset entry/entries from registry.")


@datasets_app.command("find")
def datasets_find(
    config: Path = typer.Option(..., "--config", "-c", help="Path to YAML job config."),
    backend: str = typer.Option(
        None,
        "--backend",
        "-b",
        help="Backend name to include in hash (optional, uses config backend if available).",
    ),
):
    """Find datasets matching a config file."""
    from komansim.schemas.job_schema import JobConfig
    from komansim.registry.local_registry import LocalRegistry
    from komansim.utils.hashing import config_hash
    import yaml

    # Load and validate config
    raw = yaml.safe_load(config.read_text(encoding="utf-8"))
    cfg = JobConfig.model_validate(raw)

    # Determine backend to use: prefer CLI flag, then config backend, then None
    backend_to_use = backend if backend else cfg.backend

    # Compute hashes
    from komansim.utils.hashing import canonicalize, jobspec_hash, dataset_hash
    from komansim.pipeline.manifest import _get_simdata_version

    config_dict = cfg.model_dump()
    canonical_jobspec = canonicalize(config_dict)
    simdata_version = _get_simdata_version()

    jobspec_hash_value = jobspec_hash(canonical_jobspec)
    dataset_hash_value = (
        dataset_hash(canonical_jobspec, backend_to_use, simdata_version) if backend_to_use else None
    )

    # Search registry - prefer dataset_hash, fallback to old config_hash for backwards compatibility
    registry = LocalRegistry()
    entry = None
    if dataset_hash_value:
        entry = registry.find_by_dataset_hash(dataset_hash_value)

    # Fallback to old config_hash lookup for backwards compatibility
    if not entry:
        from komansim.utils.hashing import config_hash

        if backend_to_use:
            hash_input = {**config_dict, "_backend": backend_to_use}
        else:
            hash_input = config_dict
        old_hash_value = config_hash(hash_input)
        entry = registry.find_by_config_hash(old_hash_value)

    if not entry:
        typer.echo("No matching dataset found.")
        if dataset_hash_value:
            typer.echo(f"Dataset Hash: {dataset_hash_value[:16]}...")
        if jobspec_hash_value:
            typer.echo(f"Jobspec Hash: {jobspec_hash_value[:16]}...")
        if backend_to_use:
            typer.echo(f"Note: Searched with backend '{backend_to_use}' included in dataset hash.")
        elif cfg.backend:
            typer.echo(
                f"Note: Config specifies backend '{cfg.backend}', but no matching dataset found."
            )
        else:
            typer.echo(
                "Note: No backend specified. Try using --backend flag to search with backend included."
            )
        raise typer.Exit(1)

    # Check if package exists
    package_path = entry.get("package_path")
    if package_path:
        if not Path(package_path).exists():
            typer.echo(
                f"⚠️  Warning: Dataset found but package file is missing: {package_path}", err=True
            )
            typer.echo(
                "This is an orphaned registry entry. Run 'simdata datasets cleanup' to remove it.",
                err=True,
            )
            typer.echo()

    typer.echo("Found matching dataset:")
    typer.echo(json.dumps(entry, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    app()
