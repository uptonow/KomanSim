# Isaac Sim Backend Job Configurations

This directory contains example job configurations for testing the Isaac Sim backend.

## Important: Isaac Sim Environment Requirement

⚠️ **Critical**: Isaac Sim backend **must** run inside Isaac Sim's Python environment. You cannot run it with your regular Python installation.

### Platform Support

**⚠️ macOS Limitation**: Isaac Sim is **not supported on macOS**. It only runs on:
- ✅ **Linux** (recommended)
- ✅ **Windows**

**Mac Users**: You have these options:
1. **Linux VM**: Use macOS Virtualization framework (M1/M2 Macs) to run Linux VM with Isaac Sim
2. **Cloud/Remote**: Use cloud instances or remote desktop to access Linux/Windows machines
3. **Use MuJoCo instead**: MuJoCo backend works natively on Mac and provides similar functionality

### Running Isaac Sim Jobs

**Linux:**
```bash
/path/to/isaac-sim/python.sh -m simdata.cli run --backend isaac_sim --config examples/configs/job_isaac_sim_test.yaml
```

**Windows:**
```bash
C:\path\to\isaac-sim\python.bat -m simdata.cli run --backend isaac_sim --config examples/configs/job_isaac_sim_test.yaml
```

**Note**: Replace `/path/to/isaac-sim` with your actual Isaac Sim installation path.

## Available Configurations

### 1. `job_isaac_sim_test.yaml` - Minimal Test Configuration
**Purpose**: Basic smoke test for Isaac Sim backend  
**Use Case**: Quick validation that the backend works end-to-end

**Features**:
- Minimal configuration (2 objects, 2 cameras)
- 50 frames for quick testing
- Default stage (no external USD file needed)

**Usage**:
```bash
# Validate configuration (can use regular Python)
simdata validate examples/configs/job_isaac_sim_test.yaml

# Run with Isaac Sim backend (MUST use Isaac Sim's Python)
/path/to/isaac-sim/python.sh -m simdata.cli run --backend isaac_sim --config examples/configs/job_isaac_sim_test.yaml
```

### 2. `job_isaac_sim_robot_pm.yaml` - Warehouse Bin Picking Scenario
**Purpose**: Realistic B2B robot project manager use case  
**Use Case**: Generate training data for warehouse bin picking robot

**Features**:
- **5 assets**: Storage bin + 4 objects (boxes, parts)
- **3 cameras**: Overhead, side, and wrist-mounted cameras
- **100 frames**: Sufficient for small dataset
- **High randomization**: 360° yaw rotation for object diversity
- **Realistic intrinsics**: Based on common industrial cameras

**Scenario Description**:
A robotic arm in a warehouse needs to pick objects from a storage bin. The system uses:
- **Overhead camera**: For top-down view and object detection
- **Side camera**: For depth estimation and 3D understanding
- **Wrist camera**: Close-up view from robot's perspective

**Usage**:
```bash
# Validate configuration
simdata validate examples/configs/job_isaac_sim_robot_pm.yaml

# Run with Isaac Sim backend
/path/to/isaac-sim/python.sh -m simdata.cli run --backend isaac_sim --config examples/configs/job_isaac_sim_robot_pm.yaml
```

## Current Limitations

⚠️ **Note**: The Isaac Sim backend is a functional scaffold. Most features are implemented, but rendering still needs full Replicator integration:

1. ✅ **USD Stage Loading**: Implemented - Creates default stages or loads USD files
2. ✅ **Asset Spawning**: Implemented - Loads USD assets or creates placeholder geometry
3. ✅ **Pose Setting**: Implemented - Sets asset positions via USD Xform ops
4. ✅ **Camera Creation**: Implemented - Creates camera prims with intrinsics and pose
5. ⚠️ **Rendering**: Structure implemented but returns placeholder images (zeros) - needs full Replicator integration for actual RGB/depth/seg

The backend will create USD stages, spawn assets, set up cameras, and run the simulation, but rendered images will be placeholders until Replicator is fully integrated.

## Differences from MuJoCo Backend

| Feature | Isaac Sim | MuJoCo |
|---------|-----------|--------|
| **Platform Support** | Linux & Windows only (❌ No macOS) | ✅ macOS, Linux, Windows |
| **File Format** | USD (Universal Scene Description) | MJCF (XML) |
| **Environment** | Must run in Isaac Sim's Python | Can run in regular Python |
| **Rendering** | Uses Replicator (when implemented) | Uses MuJoCo renderer |
| **Assets** | USD files | MJCF XML files |
| **Installation** | Requires Isaac Sim installation | `pip install mujoco` |

## Expected Output

When run, the job will create:

```
outputs/isaac_sim_test/
├── rgb/
│   ├── 000000.png
│   ├── 000001.png
│   └── ...
├── depth/
│   └── (empty - depth=None in scaffold)
├── seg/
│   └── (empty - seg=None in scaffold)
└── meta/
    ├── 000000.json
    ├── 000001.json
    └── ...
```

**Note**: Currently, RGB images will be black (zeros) because rendering returns placeholders until Replicator is fully integrated. Depth/seg directories will be empty because `depth=None` and `seg=None` in the scaffold.

## Customization

### Adjusting Frame Count
```yaml
num_frames: 200  # Generate more frames
```

### Changing Camera Setup
```yaml
sensors:
  - name: custom_cam
    type: camera_rgb
    pose:
      p: [x, y, z]  # Position in meters
      q: [qx, qy, qz, qw]  # Quaternion rotation
    intrinsics:
      fx: 800.0  # Focal length X
      fy: 800.0  # Focal length Y
      cx: 640.0  # Principal point X
      cy: 360.0  # Principal point Y
```

### Using Custom USD Stage
```yaml
scene:
  usd_path: "path/to/your/stage.usd"  # Load custom USD stage
```

### Adjusting Randomization
```yaml
randomization:
  random_xy: 0.3      # Larger position variation (meters)
  random_yaw_deg: 90.0  # Smaller rotation variation
```

## Implementation Status

### ✅ Fully Implemented
- Backend registration
- SimulationApp initialization
- Basic lifecycle (start/close)
- Step simulation (app.update())
- USD stage management (`load_scene`) - Creates default stages or loads USD files
- Asset spawning (`spawn_asset`) - Loads USD assets or creates placeholder geometry
- Pose setting (`set_pose`) - Updates asset positions via USD Xform ops
- Camera creation (`add_sensor`) - Creates camera prims with intrinsics and pose
- Seed-based randomization (`reset`) - Sets random seeds for reproducibility
- Graceful error handling - Works even if USD/omni imports fail

### ⚠️ Partially Implemented
- **Rendering (`render`)**: Structure implemented but returns placeholder images
  - Replicator setup is in place
  - Returns black RGB images (zeros)
  - Depth/segmentation not yet connected
  - **TODO**: Full Replicator integration to get actual rendered pixels

### 🔄 Next Steps for Full Functionality
- [ ] Complete Replicator integration for RGB rendering
- [ ] Add depth annotator for depth camera rendering
- [ ] Add segmentation annotator for semantic masks
- [ ] Improve quaternion to Euler conversion in `set_pose()`
- [ ] Set physics timestep in PhysicsScene prim
- [ ] Add semantic labels to prims for segmentation

## Next Steps

Once the Isaac Sim backend is fully implemented:

1. Replace placeholder `usd_path` values with actual USD file paths
2. Verify rendered images contain actual scene content
3. Check depth maps for proper distance values
4. Validate segmentation masks match object labels
5. Test with Isaac Sim's built-in assets (NVIDIA assets)

## Troubleshooting

### Error: "IsaacSimBackend must run inside Isaac Sim's python env"
**Solution**: Use Isaac Sim's Python launcher, not your system Python.

### Error: "No module named 'isaacsim'"
**Solution**: You're not using Isaac Sim's Python. Use the launcher script.

### Black images in output
**Expected**: The backend is a scaffold and returns placeholder zeros. This is normal until rendering is implemented.

### Empty depth/seg directories
**Expected**: The scaffold returns `depth=None` and `seg=None`, so no files are written. This is normal.

## Related Documentation

- [Isaac Sim Backend Implementation](../../simdata/backends/isaac_sim/backend.py) - Backend code
- [Job Schema](../../simdata/schemas/job_schema.py) - Configuration schema
- [MuJoCo Jobs README](./README_mujoco_jobs.md) - Similar documentation for MuJoCo

