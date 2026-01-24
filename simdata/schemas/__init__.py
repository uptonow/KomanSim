"""Deprecated: simdata.schemas is deprecated. Use komansim.schemas instead."""

import warnings

from komansim.schemas import *  # noqa: F403, F401, E402

warnings.warn(
    "The 'simdata.schemas' module is deprecated and will be removed in a future version. "
    "Please use 'komansim.schemas' instead.",
    DeprecationWarning,
    stacklevel=2,
)
