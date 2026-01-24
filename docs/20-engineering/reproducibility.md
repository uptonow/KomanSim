# Reproducibility

## Overview

Config hashing and manifest generation for reproducible datasets.

## Definitions

- **Reproducible**: Rerun the same pinned JobSpec and regenerate the dataset (or equivalent) later.
- **Deterministic**: Byte-identical outputs.
- **Best-effort**: Identical manifest, artifacts match within tolerance.

## Config Hashing

**Functions** (`simdata/utils/hashing.py`):
- `canonicalize(obj)` - Normalizes data structures (sorts keys, converts tuples to lists)
- `config_hash(obj)` - SHA256 hash of canonicalized config
- `jobspec_hash(jobspec)` - SHA256 hash of canonicalized jobspec
- `dataset_hash(jobspec, backend, version)` - SHA256 hash including backend and version

**Properties:**
- Order-insensitive (same semantic config → same hash)
- Deterministic across runs
- Includes backend and simdata version in dataset_hash

## Manifest

**Function:** `build_manifest(cfg, backend, backend_name, out_dir) -> Dict`

Generates `manifest.json` with:
- `jobspec_hash`: Hash of canonicalized config
- `dataset_hash`: Hash including backend and version
- `jobspec`: Canonicalized config
- `backend`: Backend name and version
- `runtime`: Python version, platform, simdata version, git commit
- `output`: File inventory (counts, sizes, by suffix)
- `files`: List of all files with paths and sizes
- `cache_hit`: Whether this was a cache hit

## Guarantees

**What we guarantee:**
- Manifest reproducibility (always)
- Artifact determinism depends on backend; declare determinism level in manifest

**Required pins for reproducibility:**
- JobSpec hash + spec_version
- Seeds
- Asset content hashes
- Backend adapter version
- Labeler/exporter versions
- Runtime version

**What breaks reproducibility:**
- Unpinned assets
- Changing backends without recording versions
- Non-deterministic physics without tolerance policy

## File Inventory

Automatically collects:
- Total file count and size
- Files by suffix (`.png`, `.json`, etc.)
- Complete file list with paths and sizes

## Usage

Manifest is automatically generated after job completion. No manual steps required.
