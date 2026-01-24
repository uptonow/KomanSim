# Isaac Sim Backend Smoke Tests Documentation

## Overview

This document describes the smoke test suite for the Isaac Sim backend (`tests/test_isaac_sim_backend.py`). Smoke tests verify that the backend integrates correctly with the platform and implements the required `SimBackend` protocol, without requiring full Isaac Sim functionality.

## Important: Mac Compatibility

✅ **Good News for Mac Users**: Most smoke tests work on macOS! While Isaac Sim itself doesn't run on Mac, you can still test:
- Backend registration and integration
- Protocol compliance
- Method signatures
- Error handling
- Basic structure

Tests that require actual Isaac Sim execution will be automatically skipped on Mac.

## Purpose

Smoke tests are lightweight tests that verify:
- **Interface compliance**: Backend implements the `SimBackend` protocol
- **Integration**: Backend integrates with the registry and platform
- **Error handling**: Graceful failures when Isaac Sim is not available (expected on Mac)
- **Basic functionality**: Methods exist, are callable, and return correct types
- **Data flow**: Input/output contracts are respected

These tests do **not** verify:
- Actual Isaac Sim physics simulation correctness
- Real rendering output quality
- USD asset loading from files
- Camera pose/orientation accuracy
- Depth/segmentation rendering

For full functionality testing, see integration tests (requires Linux/Windows with Isaac Sim).

## Test Categories

### 1. Registration & Integration Tests

**Purpose**: Verify backend can be discovered and used by the platform.

| Test | Description | Requires Isaac Sim | Works on Mac |
|------|-------------|-------------------|-------------|
| `test_isaac_sim_backend_registered` | Verifies backend is registered after import and can be created via registry | No | ✅ Yes |
| `test_isaac_sim_backend_implements_protocol` | Verifies backend implements `SimBackend` protocol (runtime checkable) | No | ✅ Yes |

**Why it matters**: If these fail, the backend cannot be used by the platform at all.

### 2. Initialization Tests

**Purpose**: Verify backend can be configured with various parameters.

| Test | Description | Requires Isaac Sim | Works on Mac |
|------|-------------|-------------------|-------------|
| `test_isaac_sim_backend_instantiation` | Tests constructor with defaults, custom dimensions, and extra kwargs | No | ✅ Yes |

**What it verifies**:
- Default parameters: `headless=True`, `width=1280`, `height=720`
- Custom dimensions are accepted
- Extra kwargs (like `experience`) are stored correctly

**Why it matters**: Ensures backend can be configured for different use cases (headless vs GUI, different resolutions).

### 3. Lifecycle Tests

**Purpose**: Verify backend can be started and stopped properly.

| Test | Description | Requires Isaac Sim | Works on Mac |
|------|-------------|-------------------|-------------|
| `test_isaac_sim_backend_lifecycle_without_isaac` | Tests error handling when Isaac Sim is not installed | No | ✅ Yes |
| `test_isaac_sim_backend_lifecycle` | Tests start/close cycle when Isaac Sim is installed | Yes | ⏭️ Skips |

**What it verifies**:
- `start()` raises helpful `RuntimeError` when Isaac Sim is missing (expected on Mac)
- Error message mentions "isaac" or "python env" for clarity
- `start()` and `close()` work when Isaac Sim is available (Linux/Windows only)
- Can restart after closing (idempotent behavior)

**Why it matters**: Ensures proper resource management and helpful error messages.

### 4. Core Functionality Tests

**Purpose**: Verify all protocol methods work correctly.

| Test | Description | Requires Isaac Sim | Works on Mac |
|------|-------------|-------------------|-------------|
| `test_isaac_sim_backend_basic_operations` | Tests all 9 protocol methods in a complete workflow | Yes | ⏭️ Skips |

**What it verifies**:
1. `reset(seed)` - Reset simulation state with seed
2. `load_scene(scene)` - Load scene configuration
3. `spawn_asset(asset, pose)` - Add asset, returns handle
4. `set_pose(handle, pose)` - Update asset position/orientation
5. `add_sensor(sensor)` - Add camera sensor, returns handle
6. `step(dt)` - Advance simulation by timestep
7. `render()` - Render and return `FrameBundle`

**Workflow tested**:
```
start → reset → load_scene → spawn_assets → add_sensors →
(loop: set_pose → step → render) → close
```

**Why it matters**: This is the exact workflow the pipeline uses. If this works, the backend is usable.

### 5. Interface Compliance Tests

**Purpose**: Verify all required methods exist and are callable.

| Test | Description | Requires Isaac Sim | Works on Mac |
|------|-------------|-------------------|-------------|
| `test_isaac_sim_backend_method_signatures` | Verifies all 9 protocol methods exist and are callable | No | ✅ Yes |

**Required methods**:
- `start()` / `close()` - Lifecycle management
- `reset(seed)` - State reset
- `load_scene(scene)` - Scene setup
- `spawn_asset(asset, pose)` - Asset management
- `set_pose(handle, pose)` - Pose updates
- `add_sensor(sensor)` - Sensor setup
- `step(dt)` - Simulation step
- `render()` - Frame rendering

**Why it matters**: Structural test ensuring the interface is complete.

### 6. Edge Case Tests

**Purpose**: Verify defensive programming and edge cases.

| Test | Description | Requires Isaac Sim | Works on Mac |
|------|-------------|-------------------|-------------|
| `test_isaac_sim_backend_render_returns_framebundle` | Tests `render()` returns valid output even when not initialized | No | ✅ Yes |
| `test_isaac_sim_backend_multiple_sensors` | Tests adding multiple sensors of different types | No | ✅ Yes |

**What it verifies**:
- `render()` never crashes, even in unexpected states
- Multiple sensors can be added and stored correctly
- Different sensor types (RGB, depth) are supported

**Why it matters**: Ensures robustness and supports multi-camera setups.

## Running the Tests

### Prerequisites

```bash
# Install test dependencies
pip install -e ".[dev]"
```

**Note**: Isaac Sim is NOT required for most tests. Tests will skip gracefully if Isaac Sim is not available.

### Run All Tests (Mac/Linux/Windows)

```bash
# Run all tests (tests requiring Isaac Sim will skip if not available)
pytest tests/test_isaac_sim_backend.py -v
```

**On Mac (expected output):**
```
tests/test_isaac_sim_backend.py::test_isaac_sim_backend_registered PASSED
tests/test_isaac_sim_backend.py::test_isaac_sim_backend_implements_protocol PASSED
tests/test_isaac_sim_backend.py::test_isaac_sim_backend_instantiation PASSED
tests/test_isaac_sim_backend.py::test_isaac_sim_backend_lifecycle_without_isaac PASSED
tests/test_isaac_sim_backend.py::test_isaac_sim_backend_lifecycle SKIPPED [1]
tests/test_isaac_sim_backend.py::test_isaac_sim_backend_basic_operations SKIPPED [1]
tests/test_isaac_sim_backend.py::test_isaac_sim_backend_method_signatures PASSED
tests/test_isaac_sim_backend.py::test_isaac_sim_backend_render_returns_framebundle PASSED
tests/test_isaac_sim_backend.py::test_isaac_sim_backend_multiple_sensors PASSED

[1] Isaac Sim not available (expected on Mac) - requires Linux/Windows with Isaac Sim installed
```

**On Linux/Windows with Isaac Sim:**
```
tests/test_isaac_sim_backend.py::test_isaac_sim_backend_registered PASSED
tests/test_isaac_sim_backend.py::test_isaac_sim_backend_implements_protocol PASSED
tests/test_isaac_sim_backend.py::test_isaac_sim_backend_instantiation PASSED
tests/test_isaac_sim_backend.py::test_isaac_sim_backend_lifecycle_without_isaac PASSED
tests/test_isaac_sim_backend.py::test_isaac_sim_backend_lifecycle PASSED
tests/test_isaac_sim_backend.py::test_isaac_sim_backend_basic_operations PASSED
tests/test_isaac_sim_backend.py::test_isaac_sim_backend_method_signatures PASSED
tests/test_isaac_sim_backend.py::test_isaac_sim_backend_render_returns_framebundle PASSED
tests/test_isaac_sim_backend.py::test_isaac_sim_backend_multiple_sensors PASSED
```

### Run Only Tests That Work on Mac

```bash
# Run tests that don't require Isaac Sim (all work on Mac)
pytest tests/test_isaac_sim_backend.py -v -k "not lifecycle and not basic_operations"
```

### Run Full Test Suite (Requires Isaac Sim on Linux/Windows)

```bash
# Must be on Linux/Windows with Isaac Sim installed
# Use Isaac Sim's Python to run:
/path/to/isaac-sim/python.sh -m pytest tests/test_isaac_sim_backend.py -v
```

### Run Specific Test

```bash
# Run a specific test by name
pytest tests/test_isaac_sim_backend.py::test_isaac_sim_backend_registered -v

# Run tests matching a pattern
pytest tests/test_isaac_sim_backend.py -v -k "registration"
```

## Test Dependencies

### Required
- `pytest` - Test framework (included in `[dev]` extras)
- `simdata` package - The package being tested

### Optional
- `isaacsim` - Required for full integration tests
  - Only available in Isaac Sim's Python environment
  - Only on Linux/Windows (not macOS)
  - Tests will skip gracefully if not available

## Understanding Test Failures

### Common Failures

#### `RuntimeError: IsaacSimBackend must run inside Isaac Sim's python env`
**Cause**: Isaac Sim is not installed or not using Isaac Sim's Python  
**Expected on Mac**: This is normal - the test verifies the error message is helpful  
**Solution on Linux/Windows**: Use Isaac Sim's Python launcher

#### `KeyError: Backend 'isaac_sim' not registered`
**Cause**: Backend module not imported  
**Solution**: Ensure `simdata.backends.isaac_sim.backend` is imported (happens automatically in CLI)

#### `AssertionError: Missing method: <method_name>`
**Cause**: Backend doesn't implement required protocol method  
**Solution**: Add missing method to `IsaacSimBackend` class

#### `AssertionError: isinstance(backend, SimBackend)`
**Cause**: Backend doesn't properly implement `SimBackend` protocol  
**Solution**: Ensure all protocol methods are implemented correctly

## Mac-Specific Notes

### What Works on Mac

✅ **7 out of 9 tests** run successfully on Mac:
- Backend registration
- Protocol compliance
- Instantiation
- Error handling verification
- Method signatures
- Render returns FrameBundle
- Multiple sensors

### What Skips on Mac

⏭️ **2 tests** are automatically skipped (require Isaac Sim):
- Full lifecycle test
- Basic operations test

### Why This Is Useful

Even without Isaac Sim, you can verify:
- The backend code structure is correct
- It integrates with the platform
- It implements the protocol correctly
- Error messages are helpful
- The interface is complete

This allows Mac developers to:
- Validate code changes
- Ensure protocol compliance
- Catch structural issues
- Verify error handling

## Adding New Tests

When adding new functionality to the Isaac Sim backend:

1. **Add smoke test first** - Verify the interface works
2. **Test without Isaac Sim** - Ensure graceful error handling (works on Mac)
3. **Test with Isaac Sim** - Verify actual functionality (Linux/Windows only)
4. **Document the test** - Add to this file

### Test Template

```python
def test_isaac_sim_backend_new_feature():
    """Test description.
    
    What it verifies:
    - Specific behavior 1
    - Specific behavior 2
    
    Requirements: None (or Isaac Sim must be installed)
    """
    import komansim.backends.isaac_sim.backend  # noqa: F401
    
    backend = make_backend("isaac_sim", headless=True, width=64, height=64)
    
    # Test implementation
    # ...
    
    assert expected_behavior
```

## Related Documentation

- [SimBackend Protocol](../simdata/core/backend.py) - Interface definition
- [Isaac Sim Backend Implementation](../simdata/backends/isaac_sim/backend.py) - Backend code
- [Backend Registry](../simdata/core/registry.py) - Registration system
- [Main README](../README.md) - Project overview
- [MuJoCo Backend Tests](./README_mujoco_backend_tests.md) - Similar documentation for MuJoCo

## Test Coverage Summary

| Category | Tests | Requires Isaac Sim | Works on Mac | Coverage |
|----------|-------|-------------------|-------------|----------|
| Registration | 2 | 0 | ✅ Yes | ✅ Complete |
| Initialization | 1 | 0 | ✅ Yes | ✅ Complete |
| Lifecycle | 2 | 1 | ⏭️ Partial | ✅ Complete |
| Core Operations | 1 | 1 | ⏭️ Skips | ✅ Complete |
| Interface Compliance | 1 | 0 | ✅ Yes | ✅ Complete |
| Edge Cases | 2 | 0 | ✅ Yes | ✅ Complete |
| **Total** | **9** | **2** | **7/9** | **✅ Complete** |

## Platform Comparison

| Platform | Tests Run | Tests Skipped | Notes |
|----------|-----------|---------------|-------|
| **macOS** | 7 | 2 | Most tests work, full validation possible |
| **Linux (no Isaac Sim)** | 7 | 2 | Same as Mac |
| **Linux (with Isaac Sim)** | 9 | 0 | Full test suite |
| **Windows (no Isaac Sim)** | 7 | 2 | Same as Mac |
| **Windows (with Isaac Sim)** | 9 | 0 | Full test suite |

## Maintenance

These tests should be updated when:
- The `SimBackend` protocol changes
- New backend features are added
- Error handling behavior changes
- Dependencies change

Keep this documentation in sync with the test file.

