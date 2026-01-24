"""Deprecated: simdata.pipeline is deprecated. Use komansim.pipeline instead."""

import warnings

from komansim.pipeline import *  # noqa: F403, F401, E402

warnings.warn(
    "The 'simdata.pipeline' module is deprecated and will be removed in a future version. "
    "Please use 'komansim.pipeline' instead.",
    DeprecationWarning,
    stacklevel=2,
)
