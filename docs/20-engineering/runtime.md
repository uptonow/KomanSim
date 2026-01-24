# Runtime API

## Overview

Programmatic interface for executing jobs (`simdata.runtime.run_job`).

## Function

**`run_job(config_path_or_obj, backend, out_dir=None, seed=None, use_cache=False, raise_on_failure=True) -> RunResult`**

**Parameters:**
- `config_path_or_obj`: Path to YAML config or `JobConfig` object
- `backend`: Backend name (str) or `SimBackend` instance
- `out_dir`: Optional output directory override
- `seed`: Optional seed override
- `use_cache`: Enable caching (check registry for existing dataset)
- `raise_on_failure`: Raise exception on failure (default: True)

**Returns:** `RunResult` with:
- `dataset_id`: Unique dataset identifier
- `package_path`: Path to packaged dataset
- `cache_hit`: Whether this was a cache hit
- `status`: "succeeded" or "failed"
- `error`: Error message if failed

**Raises:**
- `TypeError`: Invalid parameter types
- `FileNotFoundError`: Config file not found
- `ValueError`: Config validation failed
- `KeyError`: Backend not registered
- `RuntimeError`: Backend initialization failed

## Usage

```python
from komansim.runtime.run_job import run_job
from pathlib import Path

# From config file
result = run_job(
    config_path_or_obj=Path("examples/configs/job.yaml"),
    backend="dummy",
    use_cache=True
)

# From JobConfig object
from komansim.schemas.job_schema import JobConfig
config = JobConfig(job_name="test", num_frames=10, dt=0.1)
result = run_job(config_path_or_obj=config, backend="dummy")
```
