# User Guide

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

**Optional backends:**
- MuJoCo: `pip install mujoco`
- PyBullet: `pip install pybullet`
- Isaac Sim: Requires Isaac Sim installation

## Quick Start

```bash
# Validate config
komansim validate examples/configs/job_dummy_coco.yaml

# Run job
komansim run --backend dummy --config examples/configs/job_dummy_coco.yaml

# Use caching
komansim run --backend dummy --config examples/configs/job_dummy_coco.yaml --cache
```

## Configuration

Minimal config example:

```yaml
job_name: demo_job
out_dir: outputs/demo_job
seed: 0
num_frames: 10
dt: 0.0333333
headless: true
width: 640
height: 480

scene:
  usd_path: null
  physics_dt: 0.0166667
  dome_light_intensity: 1500.0

assets:
  - name: obj_01
    usd_path: "PATH/TO/YOUR_ASSET.usd"
    semantic_label: "object"
    scale: 1.0

sensors:
  - name: cam0
    type: camera_rgb
    pose:
      p: [1.5, 1.5, 1.2]
      q: [0.0, 0.0, 0.0, 1.0]
    intrinsics:
      fx: 500
      fy: 500
      cx: 320
      cy: 240

randomization:
  random_xy: 0.2
  random_yaw_deg: 180.0
```

**Asset format compatibility:**
- Dummy: Any (placeholders)
- MuJoCo: `.mjcf`, `.xml`
- PyBullet: `primitive://box`, `primitive://sphere`
- Isaac Sim: `.usd`, `.usda`, `.usdc`

## CLI Commands

**Main:**
- `komansim init <path>` - Generate starter config
- `komansim validate <path>` - Validate config
- `komansim run --backend <name> --config <path> [--cache]` - Run job

**Dataset management:**
- `komansim datasets list` - List all datasets
- `komansim datasets show <dataset_id>` - Show details
- `komansim datasets find --config <path>` - Find by config
- `komansim datasets cleanup` - Remove orphaned entries
- `komansim datasets clear` - Clear registry

## Backends

| Backend | Dependencies | Asset Format | Platform |
|---------|-------------|--------------|----------|
| **Dummy** | None | Any | All |
| **MuJoCo** | `pip install mujoco` | `.mjcf`, `.xml` | All |
| **PyBullet** | `pip install pybullet` | `primitive://box`, `primitive://sphere` | All |
| **Isaac Sim** | Isaac Sim installation | `.usd`, `.usda`, `.usdc` | Linux/Windows |

**Isaac Sim usage:**
```bash
/path/to/isaac-sim/python.sh -m simdata.cli run --backend isaac_sim --config <config.yaml>
```

## Output Structure

```
outputs/<job_name>/
├── rgb/              # RGB images (PNG)
├── depth/            # Depth maps
├── seg/              # Segmentation masks
├── meta/             # Frame metadata JSON
├── annotations.jsonl # Canonical annotations
├── exports/          # COCO/YOLO exports
│   ├── coco/annotations.json
│   └── yolo/
├── previews/         # Preview images
├── qa.json          # Quality metrics
└── manifest.json     # Dataset metadata
```

Package archive: `outputs/<job_name>.zip` (sibling of out_dir)

## Registry & Caching

Registry location: `~/.simdata/registry.json`

Enable caching with `--cache` flag. Cache hits are recorded in manifest.

## Troubleshooting

**Backend mismatch:** Ensure config backend matches `--backend` flag, or remove backend from config.

**Asset format mismatch:** Use assets compatible with chosen backend (see Asset Format Compatibility above).

**Cache not working:** Verify config hash matches, backend matches, and `--cache` flag is used.

See [Troubleshooting Guide](20-engineering/troubleshooting.md) for more details.
