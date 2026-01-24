"""Deprecated: simdata.registry is deprecated. Use komansim.registry instead."""

import warnings

from komansim.registry import *  # noqa: F403, F401, E402

warnings.warn(
    "The 'simdata.registry' module is deprecated and will be removed in a future version. "
    "Please use 'komansim.registry' instead.",
    DeprecationWarning,
    stacklevel=2,
)
