# Architecture

## Components

### 1. CLI/SDK
- Read + validate JobSpec
- Runtime module (`simdata.runtime`) provides programmatic API for job execution
- Local dataset registry and caching

### 2. Pipeline
- Frame generation (RGB, depth, segmentation)
- Annotation generation (canonical format)
- Export generation (COCO, YOLO)
- Manifest generation (hashes, versions, lineage)
- Package creation (zip/tar archives)

### 3. Backends
- BackendAdapter interface for simulator integration
- Supported: Dummy, MuJoCo, PyBullet, Isaac Sim
- Each backend implements `SimBackend` contract

### 4. Labelers
- Extract structured annotations from simulation data
- Bbox from segmentation mask labeler
- Extensible for additional labeler types

### 5. Exporters
- Convert canonical annotations to training formats
- COCO and YOLO exporters
- Extensible for additional formats

## Reproducibility

Reproducibility is achieved by pinning:
- Spec hash + seeds
- Assets by content hash
- Backend adapter version
- Labeler/exporter versions
- Runtime version

Some backends may be "best effort deterministic"; the manifest declares determinism level.

## Adapter Interfaces

**BackendAdapter:**
- `setup(job_spec, assets) -> ctx`
- `step(ctx) -> FrameBundle`
- `teardown(ctx)`

**FrameBundle:**
- Sensor frames (rgb/depth/etc.)
- Camera intrinsics/extrinsics
- Object IDs + poses (if available)
- Timestamps/frame index

**Labeler:**
- `label(frame_bundle, ctx) -> annotations`

**Exporter:**
- `export(frames, annotations, output_config) -> artifact_path`
