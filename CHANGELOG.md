# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-01-15

### Added
- Initial open-source release of SimData Platform SDK and CLI
- Support for multiple backends: Dummy, MuJoCo, PyBullet, Isaac Sim
- Automatic labeling: Bounding boxes and instance segmentation
- Standard export formats: COCO and YOLO
- Local dataset registry and caching system
- Reproducibility features: Config hashing, manifest generation, seed tracking
- Python SDK with `validate_config()`, `run()`, and `stats()` functions
- CLI commands for job execution and dataset management
- Comprehensive validation: Backend/asset format validation, resource limits

### Known Limitations
- Multi-sensor output is currently optimized for single-camera workflows
- Backend availability depends on optional dependencies (MuJoCo, PyBullet) or proprietary runtimes (Isaac Sim)

### Technical Details
- Python 3.10+ required
- Registry stored in `~/.simdata/`
- Output structure includes RGB images, depth maps, segmentation masks, metadata, annotations, and exports
- Package archives created at `{out_dir}.zip` by default
