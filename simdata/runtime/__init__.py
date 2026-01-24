"""Deprecated: simdata.runtime is deprecated. Use komansim.runtime instead."""

import warnings

from komansim.runtime import *  # noqa: F403, F401, E402

warnings.warn(
    "The 'simdata.runtime' module is deprecated and will be removed in a future version. "
    "Please use 'komansim.runtime' instead.",
    DeprecationWarning,
    stacklevel=2,
)
