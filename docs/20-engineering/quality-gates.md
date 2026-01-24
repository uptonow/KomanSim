# Quality Gates (Planned)

**Status:** Not yet implemented. This document describes planned functionality.

Quality gates will turn synthetic generation into a reliable **data factory** by automatically rejecting low-signal or invalid samples and resampling until the job hits its target count or a safe cap.

## Planned Gates

### 1) Visibility / min-area
- Reject if any required class has bbox area < `min_bbox_area_px`
- Reject if visible fraction < `min_visible_frac`

### 2) Label integrity
- Reject if mask is empty for an object that exists
- Reject if bbox does not enclose the mask
- Reject if class ids are missing / inconsistent

### 3) Scene validity
- Reject if no objects in view
- Reject if objects spawn out of bounds / NaNs / extreme Z values
- Reject if camera intrinsics invalid

### 4) Distribution (optional)
- Keep difficulty buckets (easy/medium/hard) based on occlusion & size
- Enforce requested distribution at the dataset level

## Resampling Policy

- Resample per-frame with `max_resample_attempts`
- If cap exceeded: mark sample as failed + record reason

## Reporting

Emit `quality_report.json` with acceptance rate, top rejection reasons, bbox area stats, and occlusion stats.
