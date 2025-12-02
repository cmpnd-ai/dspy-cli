"""DSPy CLI - A CLI tool for creating and serving DSPy projects."""

from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("dspy-cli")
except PackageNotFoundError:
    __version__ = "0.0.0"
