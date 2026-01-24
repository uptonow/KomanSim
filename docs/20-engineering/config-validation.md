# Config Validation

## Overview

Automatic validation of job configs with optional resource limits.

## Resource Limits

Optional limits (all default to `None` = no limit):

- `max_frames`: Maximum number of frames (int)
- `max_resolution`: Maximum resolution in pixels (width × height, int)
- `max_modalities`: Maximum number of sensor types (int)
- `max_total_size`: Maximum estimated dataset size in bytes (int)

## Usage

```yaml
job_name: my_job
num_frames: 5000
width: 1920
height: 1080

# Optional resource limits
max_frames: 10000
max_resolution: 2073600  # 1920×1080
max_modalities: 3
max_total_size: 10737418240  # 10 GB
```

## Validation

Validation runs automatically when:
- Config is loaded via `JobConfig.model_validate()`
- `simdata validate` command is used
- `run_job()` is called

**Errors:**
- Raises `ValueError` if limits are exceeded
- Clear error messages indicate which limit was violated
