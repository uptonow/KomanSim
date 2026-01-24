"""Deprecated: simdata.schemas.job_schema is deprecated. Use komansim.schemas.job_schema instead."""

import warnings

from komansim.schemas.job_schema import *  # noqa: F403, F401, E402

warnings.warn(
    "The 'simdata.schemas.job_schema' module is deprecated and will be removed in a future version. "
    "Please use 'komansim.schemas.job_schema' instead.",
    DeprecationWarning,
    stacklevel=2,
)
