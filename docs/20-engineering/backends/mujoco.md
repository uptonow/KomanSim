# MuJoCo Backend Documentation

## Overview

The MuJoCo backend provides real RGB, depth, and instance segmentation rendering using the MuJoCo physics simulator. It is designed to run headlessly in WSL and other headless environments using EGL or OSMesa for offscreen rendering.

## Installation

### Prerequisites

1. **MuJoCo Python package**:
   ```bash
   pip install mujoco
   ```

2. **EGL or OSMesa libraries** (for headless rendering):
   - **EGL** (preferred): Usually available on systems with NVIDIA drivers
   - **OSMesa** (fallback): Software rendering, slower but more compatible

### System Requirements

- **WSL2 with NVIDIA GPU** (tested on RTX 3080 Ti)
- **NVIDIA drivers** (for EGL support)
- **Python 3.8+**

## Configuration

### Environment Variables

Set `MUJOCO_GL` to specify the rendering backend:

```bash
# Use EGL (preferred for headless with GPU)
export MUJOCO_GL=egl

# Or use OSMesa (fallback, software rendering)
export MUJOCO_GL=osmesa
```

If `MUJOCO_GL` is not set and `headless=True`, the backend will automatically set it to `egl`.

### Job Configuration

Example minimal configuration:

```yaml
job_name: mujoco_test
out_dir: outputs/mujoco_test
seed: 42
num_frames: 100
dt: 0.0333333  # 30 FPS
headless: true
width: 1280
height: 720

scene:
  usd_path: null  # Creates default scene with floor
  physics_dt: 0.0166667  # 60 Hz physics
  dome_light_intensity: 1500.0

assets:
  - name: object_1
    usd_path: "dummy.mjcf"  # Not used, backend creates box geometry
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

The MuJoCo backend produces three types of outputs:

1. **RGB Images**: Standard color images (uint8, HxWx3)
2. **Depth Maps**: Normalized depth values (float32, HxW, range [0,1])
3. **Instance Segmentation**: Per-object masks (int32, HxW, 0=background, 1..K=instances)

### Asset Spawning

For MVP, the backend creates simple box geometries for each asset. The `usd_path` field in the asset spec is not used; the backend automatically creates a box with size based on the `scale` parameter.

**Future**: Support for loading actual MJCF files from `usd_path`.

### Camera Setup

The backend uses the first sensor in the configuration as the main camera. Camera pose is specified as:
- Position: `(x, y, z)` in world coordinates
- Orientation: Quaternion `(x, y, z, w)`

The camera automatically looks at the origin `(0, 0, 0)` and computes azimuth/elevation from the position.

### Instance Segmentation

The backend uses a **color-id rendering method** for segmentation:

1. Each object is rendered with a unique flat color
2. Colors are deterministically generated from instance IDs
3. The rendered image is analyzed to map colors back to instance IDs
4. Result is an int32 mask where:
   - `0` = background
   - `1..K` = instance IDs (one per spawned object)

This method is robust and works reliably in headless environments.

## Running Jobs

### Basic Usage

```bash
# Set rendering backend (if not already set)
export MUJOCO_GL=egl

# Run a job
simdata run --backend mujoco --config examples/configs/mujoco_smoke.yaml
```

### Smoke Test

Run the smoke test to verify the backend works:

```bash
# Enable real backend tests
export SIMDATA_REAL_BACKEND=1

# Run smoke test
pytest tests/smoke/test_smoke_mujoco.py -v
```

The smoke test verifies:
- Outputs exist (manifest, annotations, COCO, YOLO, package)
- At least one frame contains objects
- Segmentation has >1 unique value (background + objects)

## Output Format

### Metadata

Each frame's metadata includes:

```json
{
  "backend": "mujoco",
  "backend_version": "3.x.x",
  "width": 1280,
  "height": 720,
  "seg_encoding": "instance_id int32 (0=background, 1..K=instances)",
  "depth_encoding": "normalized float32 [0,1]"
}
```

### Segmentation Encoding

- **Format**: int32 numpy array (HxW)
- **Values**: 
  - `0` = background
  - `1..K` = instance IDs (one per spawned object)
- **Storage**: `.npy` files in `seg/` directory

### Depth Encoding

- **Format**: float32 numpy array (HxW)
- **Values**: Normalized depth [0, 1] (0 = near, 1 = far)
- **Storage**: `.npy` files in `depth/` directory
- **Note**: Depth values are normalized, not metric. For metric depth, additional calibration is needed.

## Troubleshooting

### EGL Not Available

**Error**: `Failed to create MuJoCo renderer` or `Could not get EGL display`

**Solutions**:
1. **Check NVIDIA drivers**: Ensure NVIDIA drivers are installed and working
   ```bash
   nvidia-smi
   ```

2. **Try OSMesa fallback**:
   ```bash
   export MUJOCO_GL=osmesa
   ```

3. **Install OSMesa libraries** (if needed):
   ```bash
   # Ubuntu/Debian
   sudo apt-get install libosmesa6-dev
   
   # Or via conda
   conda install -c conda-forge osmesa
   ```

### Segmentation Not Working

**Issue**: Segmentation mask is all zeros or has incorrect values

**Solutions**:
1. **Verify objects are spawned**: Check that `spawn_asset()` is called and handles are stored
2. **Check object visibility**: Ensure objects are within camera view
3. **Verify color-id rendering**: Check that geom colors are being set correctly

### Depth Not Available

**Issue**: `depth` is `None` in FrameBundle

**Solutions**:
1. **Check MuJoCo version**: Some versions may not expose depth buffer
2. **Verify renderer**: Ensure renderer is created successfully
3. **Depth is optional**: The pipeline works without depth

### Objects Not Moving

**Issue**: `set_pose()` doesn't update object positions

**Solutions**:
1. **Verify handles**: Ensure `spawn_asset()` returns valid handles
2. **Check free joints**: Objects need free joints to move
3. **Call forward kinematics**: Ensure `mj_forward()` is called after setting poses

### Import Errors

**Error**: `ImportError: No module named 'mujoco'`

**Solution**:
```bash
pip install mujoco
```

## Implementation Details

### Rendering Pipeline

1. **Scene Setup**: Create MuJoCo model with floor and lighting
2. **Asset Spawning**: Add bodies with free joints and box geometries
3. **Camera Setup**: Configure camera from sensor spec
4. **Rendering**:
   - Update scene with current poses
   - Render RGB using `mujoco.Renderer`
   - Render segmentation using color-id method
   - Extract depth if available

### Model Structure

The backend creates a minimal MuJoCo model:

```xml
<mujoco>
  <option timestep="0.0166667"/>
  <worldbody>
    <light name="dome" pos="0 0 5" dir="0 0 -1"/>
    <geom name="floor" type="plane" size="10 10 0.1"/>
    <!-- Spawned objects are added here -->
  </worldbody>
</mujoco>
```

### Object Management

- Each spawned asset creates a `<body>` with a `<freejoint>` and `<geom>`
- Bodies are tracked by name in `_handles` dictionary
- Instance IDs are assigned sequentially (1, 2, 3, ...)
- Poses are updated via `qpos` for free joints

## Limitations

### Current MVP Limitations

1. **Simple Geometry Only**: Assets are created as boxes, not loaded from MJCF files
2. **Single Camera**: Only the first sensor is used for rendering
3. **Normalized Depth**: Depth values are normalized, not metric
4. **Color-ID Segmentation**: Uses color-id method (not native MuJoCo segmentation API)
5. **Fixed Camera Lookat**: Camera always looks at origin

### Future Improvements

- [ ] Load actual MJCF files from `usd_path`
- [ ] Support multiple cameras
- [ ] Metric depth output
- [ ] Native MuJoCo segmentation API (if available)
- [ ] Configurable camera lookat point
- [ ] Support for more geometry types (spheres, meshes)

## Related Documentation

- [Backend Protocol](../architecture.md) - Backend interface specification
- [Job Configuration](../jobspec.md) - Job configuration format
- [Smoke Tests](../../tests/README_mujoco_backend_tests.md) - Testing documentation
- [MuJoCo Documentation](https://mujoco.readthedocs.io/) - Official MuJoCo docs

## Examples

See `examples/configs/mujoco_smoke.yaml` for a minimal working example.

## Support

For issues or questions:
1. Check this documentation
2. Review troubleshooting section
3. Check MuJoCo documentation
4. Open an issue on GitHub
