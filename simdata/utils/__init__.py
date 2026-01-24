"""Deprecated: simdata.utils is deprecated. Use komansim.utils instead."""

import warnings

from komansim.utils import *  # noqa: F403, F401, E402

warnings.warn(
    "The 'simdata.utils' module is deprecated and will be removed in a future version. "
    "Please use 'komansim.utils' instead.",
    DeprecationWarning,
    stacklevel=2,
)
