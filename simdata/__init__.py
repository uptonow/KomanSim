"""Deprecated: simdata package is deprecated. Use komansim instead.

This is a compatibility shim that forwards to komansim.
"""

import warnings

# Forward all exports from komansim
from komansim import *  # noqa: F403, F401, F405
from komansim import __version__  # noqa: F401

warnings.warn(
    "The 'simdata' package is deprecated and will be removed in a future version. "
    "Please use 'komansim' instead. "
    "Example: 'from komansim import run, stats, validate_config'",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["validate_config", "run", "stats", "__version__"]  # noqa: F405
