# Local Registry & Caching

## Overview

Tracks generated datasets and enables caching to avoid redundant generation.

## Registry Location

`~/.simdata/registry.json`

## Registry Entry

Each entry contains:
- `dataset_id`: Unique UUID
- `dataset_hash`: SHA256 hash of config + backend + simdata version
- `jobspec_hash`: SHA256 hash of canonicalized config
- `created_at`: ISO timestamp
- `backend`: Backend name
- `out_dir`: Output directory path
- `package_path`: Path to zip/tar archive

## Caching

Enable with `--cache` flag:
- First run: Generates dataset and registers it
- Subsequent runs: Detects cache hit by `dataset_hash`, returns immediately

Cache hits are recorded in manifest (`cache_hit: true`).

## CLI Commands

- `simdata datasets list` - List all datasets
- `simdata datasets show <dataset_id>` - Show details
- `simdata datasets find --config <path>` - Find by config
- `simdata datasets cleanup` - Remove orphaned entries
- `simdata datasets clear` - Clear registry

## Hash Computation

- `jobspec_hash`: SHA256 of canonicalized config (order-insensitive)
- `dataset_hash`: SHA256 of jobspec + backend + simdata version

Same config + backend + version → same hash → cache hit.
