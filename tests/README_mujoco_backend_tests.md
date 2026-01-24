# MuJoCo Backend Tests Documentation

## Overview

This document describes the test suite for the MuJoCo backend. There are two types of tests:

1. **Protocol Tests** (`tests/test_mujoco_backend.py`) - Verify backend interface compliance
2. **Integration/Smoke Tests** (`tests/smoke/test_smoke_mujoco.py`) - Verify end-to-end functionality with real rendering

## Test Files

### 1. Protocol Tests: `tests/test_mujoco_backend.py`

**Purpose**: Verify backend implements the `SimBackend` protocol correctly.

**What they test**:
- Backend registration and discovery
- Interface compliance (all required methods exist)
- Error handling (graceful failures when MuJoCo not installed)
- Basic method signatures and return types
- Lifecycle management (start/close)

**What they don't test**:
- Actual rendering output
- Real physics simulation
- End-to-end job execution

**Requirements**: 
- MuJoCo package optional (tests skip gracefully if not installed)
- No rendering backend needed

**Run**:
```bash
pytest tests/test_mujoco_backend.py -v
```

### 2. Integration/Smoke Tests: `tests/smoke/test_smoke_mujoco.py`

**Purpose**: Verify end-to-end functionality with real rendering.

**What they test**:
- Complete job execution with MuJoCo backend
- Real RGB, depth, and segmentation output
- Pipeline integration (annotations, COCO, YOLO exports)
- Output file structure and content
- Segmentation mask correctness

**Requirements**:
- MuJoCo package installed (`pip install mujoco`)
- EGL or OSMesa for headless rendering
- Environment variable: `SIMDATA_REAL_BACKEND=1`

**Run**:
```bash
export SIMDATA_REAL_BACKEND=1
pytest tests/smoke/test_smoke_mujoco.py -v
```

## Test Categories (Protocol Tests)

### 1. Registration & Integration Tests

**Purpose**: Verify backend can be discovered and used by the platform.

| Test | Description | Requires MuJoCo |
|------|-------------|-----------------|
| `test_mujoco_backend_registered` | Verifies backend is registered after import and can be created via registry | No |
| `test_mujoco_backend_implements_protocol` | Verifies backend implements `SimBackend` protocol (runtime checkable) | No |

**Why it matters**: If these fail, the backend cannot be used by the platform at all.

### 2. Initialization Tests

**Purpose**: Verify backend can be configured with various parameters.

| Test | Description | Requires MuJoCo |
|------|-------------|-----------------|
| `test_mujoco_backend_instantiation` | Tests constructor with defaults, custom dimensions, and extra kwargs | No |

**What it verifies**:
- Default parameters: `headless=True`, `width=1280`, `height=720`
- Custom dimensions are accepted
- Extra kwargs are stored in `extra` dictionary

**Why it matters**: Ensures backend can be configured for different use cases (headless vs GUI, different resolutions).

### 3. Lifecycle Tests

**Purpose**: Verify backend can be started and stopped properly.

| Test | Description | Requires MuJoCo |
|------|-------------|-----------------|
| `test_mujoco_backend_lifecycle_without_mujoco` | Tests error handling when MuJoCo is not installed | No |
| `test_mujoco_backend_lifecycle` | Tests start/close cycle when MuJoCo is installed | Yes |

**What it verifies**:
- `start()` raises helpful `RuntimeError` when MuJoCo is missing
- `start()` and `close()` work when MuJoCo is available
- Can restart after closing (idempotent behavior)

**Why it matters**: Ensures proper resource management and helpful error messages.

### 4. Core Functionality Tests

**Purpose**: Verify all protocol methods work correctly.

| Test | Description | Requires MuJoCo |
|------|-------------|-----------------|
| `test_mujoco_backend_basic_operations` | Tests all 9 protocol methods in a complete workflow | Yes |

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

| Test | Description | Requires MuJoCo |
|------|-------------|-----------------|
| `test_mujoco_backend_method_signatures` | Verifies all 9 protocol methods exist and are callable | No |

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

| Test | Description | Requires MuJoCo |
|------|-------------|-----------------|
| `test_mujoco_backend_render_returns_framebundle` | Tests `render()` returns valid output even when not initialized | No |
| `test_mujoco_backend_multiple_sensors` | Tests adding multiple sensors of different types | No |

**What it verifies**:
- `render()` never crashes, even in unexpected states
- Multiple sensors can be added and stored correctly
- Different sensor types (RGB, depth) are supported

**Why it matters**: Ensures robustness and supports multi-camera setups.

## Integration Tests (Smoke Tests)

### `test_smoke_mujoco_backend`

**Purpose**: End-to-end test with real rendering.

**What it verifies**:
- Complete job execution (10 frames)
- Output files exist (manifest, annotations, COCO, YOLO, package)
- At least one frame contains objects
- Segmentation has >1 unique value (background + objects)

**Config used**: `examples/configs/mujoco_smoke.yaml`

### `test_smoke_mujoco_segmentation_values`

**Purpose**: Verify segmentation mask correctness.

**What it verifies**:
- Segmentation is int32 array
- Values are non-negative
- Background (0) is present
- Shape matches expected dimensions

## Running the Tests

### Prerequisites

```bash
# Install test dependencies
pip install -e ".[dev]"

# Optional: Install MuJoCo for full test suite
pip install mujoco
```

### Run Protocol Tests Only

```bash
# Run all protocol tests (some will skip if MuJoCo not installed)
pytest tests/test_mujoco_backend.py -v
```

### Run Integration Tests

```bash
# Install MuJoCo first
pip install mujoco

# Set environment variable
export SIMDATA_REAL_BACKEND=1

# Run integration tests
pytest tests/smoke/test_smoke_mujoco.py -v
```

### Run All Tests

```bash
export SIMDATA_REAL_BACKEND=1
pytest tests/test_mujoco_backend.py tests/smoke/test_smoke_mujoco.py -v
```

## Test Output

**With MuJoCo installed**:
```
tests/test_mujoco_backend.py::test_mujoco_backend_registered PASSED
tests/test_mujoco_backend.py::test_mujoco_backend_implements_protocol PASSED
tests/test_mujoco_backend.py::test_mujoco_backend_instantiation PASSED
tests/test_mujoco_backend.py::test_mujoco_backend_lifecycle_without_mujoco PASSED
tests/test_mujoco_backend.py::test_mujoco_backend_lifecycle PASSED
tests/test_mujoco_backend.py::test_mujoco_backend_basic_operations PASSED
tests/test_mujoco_backend.py::test_mujoco_backend_method_signatures PASSED
tests/test_mujoco_backend.py::test_mujoco_backend_render_returns_framebundle PASSED
tests/test_mujoco_backend.py::test_mujoco_backend_multiple_sensors PASSED
tests/smoke/test_smoke_mujoco.py::test_smoke_mujoco_backend PASSED
tests/smoke/test_smoke_mujoco.py::test_smoke_mujoco_segmentation_values PASSED
```

**Without MuJoCo installed**:
```
tests/test_mujoco_backend.py::test_mujoco_backend_registered PASSED
tests/test_mujoco_backend.py::test_mujoco_backend_implements_protocol PASSED
tests/test_mujoco_backend.py::test_mujoco_backend_instantiation PASSED
tests/test_mujoco_backend.py::test_mujoco_backend_lifecycle_without_mujoco PASSED
tests/test_mujoco_backend.py::test_mujoco_backend_lifecycle SKIPPED [1]
tests/test_mujoco_backend.py::test_mujoco_backend_basic_operations SKIPPED [1]
tests/test_mujoco_backend.py::test_mujoco_backend_method_signatures PASSED
tests/test_mujoco_backend.py::test_mujoco_backend_render_returns_framebundle PASSED
tests/test_mujoco_backend.py::test_mujoco_backend_multiple_sensors PASSED

[1] MuJoCo not installed - install with 'pip install mujoco' to run full tests
```

## Test Dependencies

### Required
- `pytest` - Test framework (included in `[dev]` extras)
- `simdata` package - The package being tested

### Optional
- `mujoco` - Required for full integration tests
  - Install with: `pip install mujoco`
  - Tests will skip gracefully if not installed

## Understanding Test Failures

### Common Failures

#### `RuntimeError: MuJoCo backend requires 'mujoco' package`
**Cause**: MuJoCo is not installed  
**Solution**: Install with `pip install mujoco` or skip tests that require it

#### `KeyError: Backend 'mujoco' not registered`
**Cause**: Backend module not imported  
**Solution**: Ensure `simdata.backends.mujoco.backend` is imported (happens automatically in CLI)

#### `AssertionError: Missing method: <method_name>`
**Cause**: Backend doesn't implement required protocol method  
**Solution**: Add missing method to `MuJoCoBackend` class

#### `AssertionError: isinstance(backend, SimBackend)`
**Cause**: Backend doesn't properly implement `SimBackend` protocol  
**Solution**: Ensure all protocol methods are implemented correctly

## Adding New Tests

When adding new functionality to the MuJoCo backend:

1. **Add protocol test first** - Verify the interface works
2. **Test without MuJoCo** - Ensure graceful error handling
3. **Test with MuJoCo** - Verify actual functionality
4. **Add integration test** - Verify end-to-end if needed
5. **Document the test** - Add to this file

### Test Template

```python
def test_mujoco_backend_new_feature():
    """Test description.
    
    What it verifies:
    - Specific behavior 1
    - Specific behavior 2
    
    Requirements: None (or MuJoCo package must be installed)
    """
    import komansim.backends.mujoco.backend  # noqa: F401
    
    backend = make_backend("mujoco", headless=True, width=64, height=64)
    
    # Test implementation
    # ...
    
    assert expected_behavior
```

## Related Documentation

- [SimBackend Protocol](../../simdata/core/backend.py) - Interface definition
- [MuJoCo Backend Implementation](../../simdata/backends/mujoco/backend.py) - Backend code
- [Backend Registry](../../simdata/core/registry.py) - Registration system
- [MuJoCo Backend Docs](../../docs/20-engineering/backends/mujoco.md) - Backend documentation
- [Main README](../../README.md) - Project overview

## Test Coverage Summary

| Category | Tests | Requires MuJoCo | Coverage |
|----------|-------|----------------|----------|
| Protocol Tests | 9 | 3 | ✅ Complete |
| Integration Tests | 2 | 2 | ✅ Complete |
| **Total** | **11** | **5** | **✅ Complete** |

## Maintenance

These tests should be updated when:
- The `SimBackend` protocol changes
- New backend features are added
- Error handling behavior changes
- Dependencies change

Keep this documentation in sync with the test files.
