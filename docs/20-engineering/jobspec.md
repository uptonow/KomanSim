# JobSpec Contract (v0.1 → v0.2)

This repo currently uses a **flat JobConfig** (Pydantic) as the MVP JobSpec.
The goal is to keep the schema small while still supporting reproducible datasets.

## Current JobSpec (v0.1, implemented)
Top-level fields (see `simdata/schemas/job_schema.py`):
- `job_name`, `out_dir`, `seed`
- `num_frames`, `dt`
- `headless`, `width`, `height`
- `scene` (physics dt, dome light)
- `assets[]`, `sensors[]`
- `randomization` (pose jitter)
- resource limits: `max_frames`, `max_resolution`, `max_modalities`, `max_total_size`

## Proposed JobSpec additions (v0.2, MVP+)
These fields are recommended for MVP readiness and match the “data factory” pattern.

### outputs
Controls what artifacts are produced.
```yaml
outputs:
  canonical_annotations: true
  exports: ["coco", "yolo"]
  package: "zip"     # or "none"
```

### quality_gates
Automatic acceptance criteria + resampling policy.
```yaml
quality_gates:
  min_bbox_area_px: 400
  min_visible_frac: 0.2
  max_occlusion_frac: 0.9
  max_resample_attempts: 10
```

### sampling (optional)
Event-centric sampling around simulated events.
```yaml
sampling:
  strategy: "event"
  events: ["contact", "moved_gt", "occlusion_spike"]
  frames_per_event: 5
```

## Validation rules (MVP)
- resource limits must be enforceable at validation time
- outputs must be supported by the backend/labeler combination
- quality gates must have safe defaults (no infinite resampling)
- config hashing must be canonical (order-insensitive)

