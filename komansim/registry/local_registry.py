"""Local dataset registry for caching and tracking generated datasets.

This module provides a local registry that stores metadata about generated datasets
in ~/.simdata/registry.json, enabling caching and lookup of previously generated datasets.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4


class LocalRegistry:
    """Local registry for tracking generated datasets.

    The registry stores metadata about each dataset in ~/.simdata/registry.json.
    Each entry contains:
    - dataset_id: Unique identifier for the dataset
    - dataset_hash: SHA256 hash of jobspec + backend (+ simdata version) - primary key for cache lookup
    - jobspec_hash: SHA256 hash of canonical jobspec only (no backend)
    - config_hash: SHA256 hash of the canonicalized config (kept for backwards compatibility)
    - created_at: ISO timestamp when the dataset was created
    - backend: Backend name used (e.g., "dummy", "mujoco")
    - template: Template name (optional, None if not using template)
    - out_dir: Output directory path
    - package_path: Path to the packaged dataset (zip/tar file)
    """

    def __init__(self, registry_path: Path | None = None):
        """Initialize the local registry.

        Args:
            registry_path: Optional custom path for registry.json.
                          Defaults to ~/.simdata/registry.json
        """
        if registry_path is None:
            home = Path.home()
            self.registry_dir = home / ".simdata"
            self.registry_path = self.registry_dir / "registry.json"
        else:
            self.registry_path = Path(registry_path)
            self.registry_dir = self.registry_path.parent

        # Ensure registry directory exists
        self.registry_dir.mkdir(parents=True, exist_ok=True)

        # Load existing registry or create empty one
        self._data: Dict[str, Dict[str, Any]] = self._load()

    def _load(self) -> Dict[str, Dict[str, Any]]:
        """Load registry data from disk.

        Returns:
            Dictionary mapping dataset_id to entry data
        """
        if not self.registry_path.exists():
            return {}

        try:
            with open(self.registry_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                # Ensure it's a dict mapping dataset_id to entries
                if isinstance(data, dict):
                    return data
                else:
                    # Legacy format: list of entries
                    return {entry["dataset_id"]: entry for entry in data if "dataset_id" in entry}
        except (json.JSONDecodeError, KeyError, TypeError):
            # If registry is corrupted, start fresh
            return {}

    def _save(self) -> None:
        """Save registry data to disk."""
        with open(self.registry_path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2, ensure_ascii=False)

    def register(
        self,
        dataset_hash: str,
        backend: str,
        out_dir: Path | str,
        package_path: Path | str | None = None,
        template: str | None = None,
        dataset_id: str | None = None,
        update_existing: bool = True,
        jobspec_hash: str | None = None,
        config_hash: str | None = None,
    ) -> str:
        """Register a new dataset in the registry.

        Args:
            dataset_hash: SHA256 hash of jobspec + backend (+ simdata version) - primary key
            backend: Backend name (e.g., "dummy", "mujoco")
            out_dir: Output directory path
            package_path: Optional path to packaged dataset file
            template: Optional template name
            dataset_id: Optional dataset ID (generated if not provided)
            update_existing: If True, update existing entry with same dataset_hash instead of creating duplicate
            jobspec_hash: Optional SHA256 hash of canonical jobspec only (no backend)
            config_hash: Optional old config_hash for backwards compatibility

        Returns:
            The dataset_id of the registered dataset
        """
        # Check if entry with same dataset_hash already exists
        if update_existing:
            existing_entry = self.find_by_dataset_hash(dataset_hash)
            if existing_entry:
                # Update existing entry instead of creating duplicate
                existing_id = existing_entry["dataset_id"]
                update_data = {
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "backend": backend,
                    "template": template,
                    "out_dir": str(out_dir),
                    "package_path": str(package_path) if package_path else None,
                }
                if jobspec_hash is not None:
                    update_data["jobspec_hash"] = jobspec_hash
                if config_hash is not None:
                    update_data["config_hash"] = config_hash
                self._data[existing_id].update(update_data)
                self._save()
                return existing_id

        # Create new entry
        if dataset_id is None:
            dataset_id = str(uuid4())

        entry = {
            "dataset_id": dataset_id,
            "dataset_hash": dataset_hash,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "backend": backend,
            "template": template,
            "out_dir": str(out_dir),
            "package_path": str(package_path) if package_path else None,
        }

        if jobspec_hash is not None:
            entry["jobspec_hash"] = jobspec_hash
        if config_hash is not None:
            entry["config_hash"] = config_hash

        self._data[dataset_id] = entry
        self._save()

        return dataset_id

    def find_by_dataset_hash(self, dataset_hash: str) -> Optional[Dict[str, Any]]:
        """Find a dataset entry by dataset hash (primary lookup method).

        Args:
            dataset_hash: SHA256 hash of jobspec + backend (+ simdata version)

        Returns:
            Entry dictionary if found, None otherwise
        """
        for entry in self._data.values():
            if entry.get("dataset_hash") == dataset_hash:
                return entry.copy()
        return None

    def find_by_config_hash(self, config_hash: str) -> Optional[Dict[str, Any]]:
        """Find a dataset entry by old config hash (backwards compatibility).

        Args:
            config_hash: SHA256 hash of the canonicalized config (old format)

        Returns:
            Entry dictionary if found, None otherwise
        """
        for entry in self._data.values():
            if entry.get("config_hash") == config_hash:
                return entry.copy()
        return None

    def find_by_dataset_id(self, dataset_id: str) -> Optional[Dict[str, Any]]:
        """Find a dataset entry by dataset ID.

        Args:
            dataset_id: Dataset ID to look up

        Returns:
            Entry dictionary if found, None otherwise
        """
        entry = self._data.get(dataset_id)
        if entry:
            return entry.copy()
        return None

    def list_all(self) -> List[Dict[str, Any]]:
        """List all datasets in the registry.

        Returns:
            List of all entry dictionaries, sorted by created_at (newest first)
        """
        entries = list(self._data.values())
        # Sort by created_at descending (newest first)
        entries.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return entries

    def update_package_path(self, dataset_id: str, package_path: Path | str) -> None:
        """Update the package_path for an existing dataset entry.

        Args:
            dataset_id: Dataset ID to update
            package_path: New package path

        Raises:
            KeyError: If dataset_id is not found
        """
        if dataset_id not in self._data:
            raise KeyError(f"Dataset ID not found: {dataset_id}")

        self._data[dataset_id]["package_path"] = str(package_path)
        self._save()

    def delete(self, dataset_id: str) -> bool:
        """Delete a dataset entry from the registry.

        Args:
            dataset_id: Dataset ID to delete

        Returns:
            True if entry was deleted, False if not found
        """
        if dataset_id in self._data:
            del self._data[dataset_id]
            self._save()
            return True
        return False

    def clear(self) -> None:
        """Clear all entries from the registry."""
        self._data.clear()
        self._save()

    def cleanup_orphaned(self) -> int:
        """Remove entries where package_path doesn't exist.

        Returns:
            Number of entries removed
        """
        removed_count = 0
        to_remove = []

        for dataset_id, entry in self._data.items():
            package_path = entry.get("package_path")
            if package_path:
                if not Path(package_path).exists():
                    to_remove.append(dataset_id)

        for dataset_id in to_remove:
            del self._data[dataset_id]
            removed_count += 1

        if removed_count > 0:
            self._save()

        return removed_count

    def cleanup_duplicates(self, keep_newest: bool = True) -> int:
        """Remove duplicate entries with the same dataset_hash, keeping one per hash.

        Args:
            keep_newest: If True, keep the newest entry (by created_at). If False, keep the oldest.

        Returns:
            Number of entries removed
        """
        from collections import defaultdict

        # Group entries by dataset_hash (preferred) or config_hash (fallback for old entries)
        by_hash: Dict[str, List[tuple[str, Dict[str, Any]]]] = defaultdict(list)
        for dataset_id, entry in self._data.items():
            # Prefer dataset_hash, fallback to config_hash for backwards compatibility
            hash_key = entry.get("dataset_hash") or entry.get("config_hash")
            if hash_key:
                by_hash[hash_key].append((dataset_id, entry))

        removed_count = 0
        to_remove = []

        # For each hash with multiple entries, keep one and mark others for removal
        for hash_key, entries in by_hash.items():
            if len(entries) > 1:
                # Sort by created_at (newest first if keep_newest, oldest first otherwise)
                entries.sort(key=lambda x: x[1].get("created_at", ""), reverse=keep_newest)
                # Keep the first one, remove the rest
                for dataset_id, _ in entries[1:]:
                    to_remove.append(dataset_id)

        for dataset_id in to_remove:
            del self._data[dataset_id]
            removed_count += 1

        if removed_count > 0:
            self._save()

        return removed_count

    def find_by_dataset_hash_with_validation(self, dataset_hash: str) -> Optional[Dict[str, Any]]:
        """Find a dataset entry by dataset hash and verify package exists.

        Args:
            dataset_hash: SHA256 hash of jobspec + backend (+ simdata version)

        Returns:
            Entry dictionary if found and package exists, None otherwise
        """
        entry = self.find_by_dataset_hash(dataset_hash)
        if entry and entry.get("package_path"):
            if Path(entry["package_path"]).exists():
                return entry
        return None

    def find_by_config_hash_with_validation(self, config_hash: str) -> Optional[Dict[str, Any]]:
        """Find a dataset entry by old config hash and verify package exists (backwards compatibility).

        Args:
            config_hash: SHA256 hash of the canonicalized config (old format)

        Returns:
            Entry dictionary if found and package exists, None otherwise
        """
        entry = self.find_by_config_hash(config_hash)
        if entry and entry.get("package_path"):
            if Path(entry["package_path"]).exists():
                return entry
        return None
