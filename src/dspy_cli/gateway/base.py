"""Base Gateway class for all gateway types."""

from abc import ABC


class Gateway(ABC):
    """Base class for all gateways.
    
    A gateway controls how data flows into and out of a DSPy pipeline.
    Subclasses define specific input/output transformation patterns.
    """
    pass
