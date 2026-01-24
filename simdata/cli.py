"""Deprecated: simdata.cli is deprecated. Use komansim.cli instead."""

import warnings

from komansim.cli import *  # noqa: F403, F401, E402

warnings.warn(
    "The 'simdata.cli' module is deprecated and will be removed in a future version. "
    "Please use 'komansim.cli' instead.",
    DeprecationWarning,
    stacklevel=2,
)
