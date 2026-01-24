"""Tests for simdata.utils.hashing module."""

from komansim.utils.hashing import canonicalize, config_hash, dumps_canonical


def test_canonicalize_dict_key_order():
    """Test that canonicalize produces same result regardless of dict key order."""
    dict1 = {"a": 1, "b": 2, "c": 3}
    dict2 = {"c": 3, "a": 1, "b": 2}
    dict3 = {"b": 2, "c": 3, "a": 1}

    result1 = canonicalize(dict1)
    result2 = canonicalize(dict2)
    result3 = canonicalize(dict3)

    assert result1 == result2 == result3


def test_canonicalize_nested_dict():
    """Test that canonicalize works with nested dictionaries."""
    dict1 = {"outer": {"inner1": 1, "inner2": 2}, "other": "value"}
    dict2 = {"other": "value", "outer": {"inner2": 2, "inner1": 1}}

    result1 = canonicalize(dict1)
    result2 = canonicalize(dict2)

    assert result1 == result2


def test_canonicalize_list_vs_tuple():
    """Test that canonicalize converts tuples to lists."""
    dict1 = {"items": [1, 2, 3]}
    dict2 = {"items": (1, 2, 3)}

    result1 = canonicalize(dict1)
    result2 = canonicalize(dict2)

    assert result1 == result2


def test_dumps_canonical_stable():
    """Test that dumps_canonical produces stable output."""
    dict1 = {"a": 1, "b": 2, "c": 3}
    dict2 = {"c": 3, "a": 1, "b": 2}

    json1 = dumps_canonical(dict1)
    json2 = dumps_canonical(dict2)

    assert json1 == json2


def test_config_hash_stable_same_dict():
    """Test that config_hash produces same hash for same dict regardless of key order."""
    dict1 = {"a": 1, "b": 2, "c": {"d": 3, "e": 4}}
    dict2 = {"c": {"e": 4, "d": 3}, "b": 2, "a": 1}

    hash1 = config_hash(dict1)
    hash2 = config_hash(dict2)

    assert hash1 == hash2
    assert len(hash1) == 64  # SHA256 hex digest length


def test_config_hash_different_for_different_values():
    """Test that config_hash produces different hash if leaf value differs."""
    dict1 = {"a": 1, "b": 2, "c": 3}
    dict2 = {"a": 1, "b": 2, "c": 4}  # Different value

    hash1 = config_hash(dict1)
    hash2 = config_hash(dict2)

    assert hash1 != hash2


def test_config_hash_different_for_different_keys():
    """Test that config_hash produces different hash if keys differ."""
    dict1 = {"a": 1, "b": 2}
    dict2 = {"a": 1, "c": 2}  # Different key

    hash1 = config_hash(dict1)
    hash2 = config_hash(dict2)

    assert hash1 != hash2


def test_config_hash_nested_structures():
    """Test that config_hash works correctly with nested structures."""
    dict1 = {
        "job_name": "test",
        "sensors": [{"name": "cam0", "type": "rgb"}, {"name": "cam1", "type": "depth"}],
        "scene": {"usd_path": None, "intensity": 1500.0},
    }
    dict2 = {
        "scene": {"intensity": 1500.0, "usd_path": None},
        "job_name": "test",
        "sensors": [{"type": "rgb", "name": "cam0"}, {"type": "depth", "name": "cam1"}],
    }

    hash1 = config_hash(dict1)
    hash2 = config_hash(dict2)

    assert hash1 == hash2


def test_config_hash_with_none():
    """Test that config_hash handles None values correctly."""
    dict1 = {"a": 1, "b": None, "c": 3}
    dict2 = {"c": 3, "a": 1, "b": None}

    hash1 = config_hash(dict1)
    hash2 = config_hash(dict2)

    assert hash1 == hash2
