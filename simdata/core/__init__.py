"""Deprecated: simdata.core is deprecated. Use komansim.core instead."""

import warnings

from komansim.core import *  # noqa: F403, F401, E402

warnings.warn(
    "The 'simdata.core' module is deprecated and will be removed in a future version. "
    "Please use 'komansim.core' instead.",
    DeprecationWarning,
    stacklevel=2,
)
