"""Gateway discovery for DSPy modules.

This module provides utilities to find and instantiate gateways for DSPy modules.
Gateways can be specified in two ways:

1. Module attribute: The DSPy module class has a `gateway` class attribute
   pointing to a Gateway subclass.
   
   class MyModule(dspy.Module):
       gateway = MyCustomGateway
       
2. Default: If no gateway is specified, IdentityGateway is used for
   backward compatibility (HTTP inputs == pipeline inputs).
"""

import logging
from typing import Optional, Type

from dspy_cli.discovery import DiscoveredModule
from dspy_cli.gateway import APIGateway, CronGateway, Gateway, IdentityGateway

logger = logging.getLogger(__name__)


def get_gateway_for_module(module: DiscoveredModule) -> Gateway:
    """Get or create the gateway instance for a discovered module.
    
    Checks if the module class has a `gateway` attribute pointing to a
    Gateway subclass. If so, instantiates and returns it. Otherwise,
    returns an IdentityGateway instance for backward compatibility.
    
    Args:
        module: DiscoveredModule to get gateway for
        
    Returns:
        Gateway instance (APIGateway, CronGateway, or subclass)
    """
    gateway_class = get_gateway_class(module)
    
    if gateway_class is None:
        logger.debug(f"No gateway for {module.name}, using IdentityGateway")
        return IdentityGateway()
    
    try:
        gateway = gateway_class()
        logger.info(f"Using {gateway_class.__name__} for {module.name}")
        return gateway
    except Exception as e:
        logger.warning(
            f"Failed to instantiate {gateway_class.__name__} for {module.name}: {e}. "
            f"Falling back to IdentityGateway."
        )
        return IdentityGateway()


def get_gateway_class(module: DiscoveredModule) -> Optional[Type[Gateway]]:
    """Extract the gateway class from a module if specified.
    
    Args:
        module: DiscoveredModule to check
        
    Returns:
        Gateway subclass if specified, None otherwise
    """
    return module.gateway_class


def _is_gateway_class(obj) -> bool:
    """Check if an object is a Gateway subclass (not instance)."""
    try:
        return isinstance(obj, type) and issubclass(obj, Gateway)
    except TypeError:
        return False


def is_api_gateway(gateway: Gateway) -> bool:
    """Check if a gateway is an APIGateway (handles HTTP requests)."""
    return isinstance(gateway, APIGateway)


def is_cron_gateway(gateway: Gateway) -> bool:
    """Check if a gateway is a CronGateway (scheduled execution)."""
    return isinstance(gateway, CronGateway)
