"""Canonical hashing utilities for reproducible config hashing."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def canonicalize(obj: Any) -> Any:
    """Recursively canonicalize a data structure for stable hashing.

    This function normalizes data structures so that semantically equivalent
    objects produce the same hash, regardless of:
    - Dictionary key order
    - List vs tuple
    - None vs missing keys

    Args:
        obj: The object to canonicalize (dict, list, tuple, or primitive)

    Returns:
        Canonicalized version of the object
    """
    if obj is None:
        return None
    elif isinstance(obj, (str, int, float, bool)):
        return obj
    elif isinstance(obj, dict):
        # Sort keys and recursively canonicalize values
        return {str(k): canonicalize(v) for k, v in sorted(obj.items())}
    elif isinstance(obj, (list, tuple)):
        # Convert to list and recursively canonicalize elements
        return [canonicalize(item) for item in obj]
    else:
        # For other types, convert to string representation
        return str(obj)


def dumps_canonical(obj: Any) -> str:
    """Serialize an object to a canonical JSON string.

    This function:
    1. Canonicalizes the object (normalizes structure)
    2. Serializes to JSON with consistent formatting

    Args:
        obj: The object to serialize

    Returns:
        Canonical JSON string
    """
    canonical = canonicalize(obj)
    return json.dumps(canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def config_hash(obj: Any) -> str:
    """Compute a stable hash of a configuration object.

    The hash is computed from the canonical JSON representation,
    ensuring that semantically equivalent configs produce the same hash
    regardless of key order or formatting.

    Args:
        obj: The configuration object to hash (typically a dict or Pydantic model)

    Returns:
        Hexadecimal SHA256 hash string
    """
    canonical_json = dumps_canonical(obj)
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


def jobspec_hash(jobspec: Any) -> str:
    """Compute hash of canonical jobspec only (no backend).

    This hash represents the job specification independently of the backend
    used to execute it. Useful for identifying equivalent jobspecs across
    different backends.

    Args:
        jobspec: The jobspec object to hash (typically a dict or Pydantic model)

    Returns:
        Hexadecimal SHA256 hash string
    """
    canonical_json = dumps_canonical(jobspec)
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


def dataset_hash(jobspec: Any, backend_name: str, simdata_version: str | None = None) -> str:
    """Compute hash of jobspec + backend name (+ optional simdata version).

    This hash (also known as cache_key) uniquely identifies a dataset generated
    from a specific jobspec using a specific backend. The optional simdata_version
    can be included for version-aware caching.

    Args:
        jobspec: The jobspec object to hash (typically a dict or Pydantic model)
        backend_name: Name of the backend (e.g., "dummy", "isaac_sim")
        simdata_version: Optional simdata package version for version-aware caching

    Returns:
        Hexadecimal SHA256 hash string
    """
    # Build hash input: jobspec + backend name + optional version
    hash_input = {
        "jobspec": canonicalize(jobspec),
        "backend": backend_name,
    }
    if simdata_version is not None:
        hash_input["simdata_version"] = simdata_version

    canonical_json = dumps_canonical(hash_input)
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()
