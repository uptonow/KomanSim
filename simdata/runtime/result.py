"""Deprecated: simdata.runtime.result is deprecated. Use komansim.runtime.result instead."""

import warnings

from komansim.runtime.result import *  # noqa: F403, F401, E402

warnings.warn(
    "The 'simdata.runtime.result' module is deprecated and will be removed in a future version. "
    "Please use 'komansim.runtime.result' instead.",
    DeprecationWarning,
    stacklevel=2,
)
