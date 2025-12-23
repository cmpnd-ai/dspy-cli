"""Base Gateway class for all gateway types."""

from abc import ABC


class Gateway(ABC):
    """Base class for all gateways.
    
    A gateway controls how data flows into and out of a DSPy pipeline.
    Subclasses define specific input/output transformation patterns.
    """

    def setup(self) -> None:
        """Optional initialization hook.
        
        Called once when the gateway is registered. Use for:
        - Validating configuration
        - Creating clients
        - Reading environment variables
        
        Raise an exception to indicate setup failure.
        """
        pass

    def shutdown(self) -> None:
        """Optional cleanup hook.
        
        Called when the server is shutting down. Use for:
        - Closing connections
        - Flushing buffers
        - Releasing resources
        """
        pass
