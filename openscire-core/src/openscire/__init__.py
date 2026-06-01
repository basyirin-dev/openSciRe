# SPDX-License-Identifier: Apache-2.0
"""openSciRe Core — local-first, epistemically honest research AI for scientists."""

try:
    from importlib.metadata import version as _version

    __version__ = _version("openscire-core")
except ImportError:
    __version__ = "0.1.0"
