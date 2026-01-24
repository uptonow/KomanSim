# PyBullet Backend Documentation

## Overview

The PyBullet backend provides real RGB, depth, and instance segmentation rendering using the PyBullet physics simulator. It is designed to run headlessly in WSL and other headless environments using DIRECT mode with TinyRenderer for offscreen rendering.

## Installation

### Prerequisites

1. **PyBullet Python package**:
   ```bash
   pip install pybullet
   ```
   
   Note: `pybullet_data` is included with the `pybullet` package and doesn't need to be installed separately.

### System Requirements

- **WSL2** (tested, but works on any Linux/Windows/Mac)
- **Python 3.8+**

## Configuration

### Environment Variables

No special environment variables are required. PyBullet uses DIRECT mode by default, which is headless-friendly and works in WSL without GPU acceleration.

### Job Configuration

Example minimal configuration:

```yaml
job_name: pybullet_test
out_dir: outputs/pybullet_test
seed: 42
num_frames: 100
dt: 0.0333333  # 30 FPS
headless: true
width: 1280
height: 720

scene:
  usd_path: null  # Creates default scene with ground plane
  physics_dt: 0.0166667  # 60 Hz physics
  dome_light_intensity: 1500.0

assets:
  - name: object_1
    usd_path: "primitive://box"  # Creates a box primitive
    semantic_label: "object"
    scale: 1.0

  - name: object_2
    usd_path: "primitive://sphere"  # Creates a sphere primitive
    semantic_label: "object"
    scale: 1.0

sensors:
  - name: main_camera
    type: camera_rgb
    pose:
      p: [2.0, 2.0, 1.5]  # Camera position (x, y, z)
      q: [0.0, 0.0, 0.0, 1.0]  # Quaternion (x, y, z, w)
    intrinsics:
      fx: 800.0
      fy: 800.0
      cx: 640.0
      cy: 360.0

randomization:
  random_xy: 0.2
  random_yaw_deg: 180.0
```

## Features

### Rendering Outputs

The PyBullet backend produces three types of outputs:

1. **RGB Images**: Standard color images (uint8, HxWx3)
2. **Depth Maps**: Metric depth values in meters (float32, HxW)
3. **Instance Segmentation**: Per-object masks (int32, HxW, 0=background, 1..K=instances)

### Asset Spawning

The backend supports primitive assets:

- `primitive://box` - Creates a box geometry
- `primitive://sphere` - Creates a sphere geometry

For non-primitive assets (not starting with `primitive://`), the backend falls back to creating a box using the `scale` parameter.

**Future**: Support for loading actual URDF/SDF files from `usd_path`.

### Camera Setup

The backend uses PyBullet's `getCameraImage` API with:
- **TinyRenderer**: Software renderer (ER_TINY_RENDERER) for headless rendering
- **Segmentation flags**: ER_SEGMENTATION_MASK_OBJECT_AND_LINKINDEX for instance segmentation

Camera intrinsics are converted to a projection matrix. If intrinsics are not provided, a default FOV of 60 degrees is used.

### Scene Setup

The backend automatically:
- Creates a ground plane (uses `pybullet_data` if available, otherwise creates a static box)
- Sets gravity to -9.8 m/s² in Z direction
- Configures physics timestep from `scene.physics_dt`

## Running Tests

### Smoke Test

To run the smoke test:

```bash
pip install pybullet
SIMDATA_REAL_BACKEND=1 pytest -m smoke -k pybullet -q
```

Or run directly:

```bash
simdata run --backend pybullet --config examples/configs/pybullet_smoke.yaml
```

## Technical Details

### DIRECT Mode

PyBullet uses DIRECT mode by default, which:
- Works headlessly without a display server
- Does not require GPU acceleration
- Uses TinyRenderer for software rendering
- Is ideal for WSL and CI environments

### Depth Conversion

Depth buffers from PyBullet are normalized [0, 1]. The backend converts them to metric depth using:

```
z = far * near / (far - (far - near) * depthBuffer)
```

Where `near=0.01` and `far=10.0` by default.

### Segmentation Encoding

PyBullet returns segmentation masks with `objectUniqueId` encoded in the buffer. The backend:
1. Extracts `objectUniqueId = seg_raw & ((1<<24)-1)`
2. Maps `objectUniqueId` to `instance_id` using the internal mapping
3. Outputs int32 array where `0=background` and `1..K=instances`

## Limitations

- **Primitive assets only**: Currently supports `primitive://box` and `primitive://sphere`
- **Software rendering**: Uses TinyRenderer (slower than GPU-accelerated rendering)
- **Simple scene**: Default scene only includes a ground plane

## Troubleshooting

### Import Error

If you get `ImportError: No module named 'pybullet'`:
```bash
pip install pybullet
```

### Rendering Issues

If rendering fails, ensure:
- PyBullet is installed correctly
- The backend is using DIRECT mode (default)
- No display server is required (DIRECT mode is headless)

## Related Documentation

- [Backend Protocol](../architecture.md) - Backend interface specification
- [Job Configuration](../jobspec.md) - Job configuration format
- [Smoke Tests](../../../tests/smoke/test_smoke_pybullet.py) - Testing documentation
- [PyBullet Documentation](https://docs.google.com/document/d/10sXEhzFRSnvFcl3XxNGhnD4N2SedqwdAvK3dsihxVUA/) - Official PyBullet docs

## Examples

See `examples/configs/pybullet_smoke.yaml` for a minimal working example.

## Support

For issues or questions:
1. Check this documentation
2. Review troubleshooting section
3. Check PyBullet documentation
4. Open an issue on GitHub
