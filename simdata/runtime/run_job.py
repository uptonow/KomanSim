"""Deprecated: simdata.runtime.run_job is deprecated. Use komansim.runtime.run_job instead."""

import warnings

from komansim.runtime.run_job import *  # noqa: F403, F401, E402

warnings.warn(
    "The 'simdata.runtime.run_job' module is deprecated and will be removed in a future version. "
    "Please use 'komansim.runtime.run_job' instead.",
    DeprecationWarning,
    stacklevel=2,
)
