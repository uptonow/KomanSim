# MuJoCo Backend Job Configurations

This directory contains example job configurations for the MuJoCo backend, organized by complexity and use case.

## Configuration Files

### 1. `mujoco_smoke.yaml` - Minimal Smoke Test
**Purpose**: Quick validation that the backend works end-to-end  
**Complexity**: Minimal  
**Use Case**: CI/CD testing, quick verification

**Features**:
- 10 frames at 320x240 resolution (fast)
- 2 simple test objects
- 1 camera (RGB)
- Minimal resource usage

**Usage**:
```bash
# Run smoke test
simdata run --backend mujoco --config examples/configs/mujoco_smoke.yaml

# Or run via pytest
export SIMDATA_REAL_BACKEND=1
pytest tests/smoke/test_smoke_mujoco.py -v
```

### 2. `mujoco_basic.yaml` - Basic Test Configuration
**Purpose**: Standard testing and development  
**Complexity**: Medium  
**Use Case**: Development, debugging, feature testing

**Features**:
- 50 frames at 1280x720 resolution
- 2 test objects
- 2 cameras (RGB + depth)
- Balanced performance and detail

**Usage**:
```bash
# Validate configuration
simdata validate examples/configs/mujoco_basic.yaml

# Run with MuJoCo backend
simdata run --backend mujoco --config examples/configs/mujoco_basic.yaml
```

### 3. `mujoco_warehouse.yaml` - Warehouse Bin Picking Scenario
**Purpose**: Realistic B2B robot project manager use case  
**Complexity**: Full scenario  
**Use Case**: Production data generation, realistic training datasets

**Features**:
- 100 frames at 1280x720 resolution
- 5 objects (storage bin + 4 items: boxes, parts)
- 3 cameras (overhead, side, wrist-mounted)
- High randomization (360° yaw rotation)
- Realistic camera intrinsics

**Scenario Description**:
A robotic arm in a warehouse needs to pick objects from a storage bin. The system uses:
- **Overhead camera**: For top-down view and object detection
- **Side camera**: For depth estimation and 3D understanding  
- **Wrist camera**: Close-up view from robot's perspective

**Usage**:
```bash
# Validate configuration
simdata validate examples/configs/mujoco_warehouse.yaml

# Run with MuJoCo backend
simdata run --backend mujoco --config examples/configs/mujoco_warehouse.yaml
```

## Quick Reference

| Config | Frames | Resolution | Objects | Cameras | Use Case |
|--------|--------|------------|---------|---------|----------|
| `mujoco_smoke.yaml` | 10 | 320x240 | 2 | 1 | Quick testing |
| `mujoco_basic.yaml` | 50 | 1280x720 | 2 | 2 | Development |
| `mujoco_warehouse.yaml` | 100 | 1280x720 | 5 | 3 | Production |

## Expected Output

When run, each job creates an output directory with:

```
outputs/{job_name}/
├── rgb/              # RGB images (PNG)
├── depth/            # Depth maps (NPY, float32)
├── seg/              # Segmentation masks (NPY, int32)
├── meta/             # Per-frame metadata (JSON)
├── annotations.jsonl # Canonical annotations
├── manifest.json     # Job manifest
└── exports/          # Standard format exports
    ├── coco.json     # COCO format
    └── yolo/         # YOLO format labels
```

A package file `{job_name}.zip` is also created in the parent directory.

## Customization

### Adjusting Frame Count
```yaml
num_frames: 200  # Generate more frames
```

### Changing Resolution
```yaml
width: 1920
height: 1080
```

### Adding More Objects
```yaml
assets:
  - name: object_3
    usd_path: "dummy.mjcf"
    semantic_label: "object"
    scale: 1.0
```

### Adjusting Randomization
```yaml
randomization:
  random_xy: 0.3      # Larger position variation (meters)
  random_yaw_deg: 90.0  # Smaller rotation variation
```

## Backend Status

✅ **Fully Functional**: The MuJoCo backend now produces real RGB, depth, and segmentation outputs.

**Current Features**:
- Real offscreen rendering (EGL/OSMesa)
- Instance segmentation via color-id method
- Depth rendering (normalized)
- Object spawning and pose updates
- Full pipeline integration (annotations, COCO, YOLO)

**Limitations**:
- Assets are created as simple boxes (MJCF file loading not yet implemented)
- Single camera used for rendering (first sensor)
- Depth values are normalized, not metric

## Related Documentation

- [MuJoCo Backend Documentation](../../docs/20-engineering/backends/mujoco.md) - Backend implementation details
- [MuJoCo Backend Tests](../../tests/README_mujoco_backend_tests.md) - Test documentation
- [Job Schema](../../simdata/schemas/job_schema.py) - Configuration schema
