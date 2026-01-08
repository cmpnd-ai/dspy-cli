"""Gateway discovery for DSPy modules.

This module provides utilities to find and instantiate gateways for DSPy modules.
Gateways can be specified in several ways:

1. Single gateway: `gateway = MyCustomGateway`
2. Multiple gateways: `gateway = [CronGateway, APIGateway]`
3. Default: If no gateway is specified, IdentityGateway is used for
   backward compatibility (HTTP inputs == pipeline inputs).

Example with multiple gateways:
    class MyModule(dspy.Module):
        gateway = [JobPostingGateway, IdentityGateway]  # Cron + HTTP
"""

import logging
from typing import List, Optional, Type

from dspy_cli.discovery import DiscoveredModule
from dspy_cli.gateway import APIGateway, CronGateway, Gateway, IdentityGateway

logger = logging.getLogger(__name__)


def get_gateways_for_module(module: DiscoveredModule) -> List[Gateway]:
    """Get all gateway instances for a discovered module.

    Instantiates all gateway classes specified on the module. If no gateways
    are specified, returns a list with a single IdentityGateway for backward
    compatibility.

    Args:
        module: DiscoveredModule to get gateways for

    Returns:
        List of Gateway instances
    """
    gateway_classes = module.gateway_classes or []

    if not gateway_classes:
        logger.debug(f"No gateways for {module.name}, using IdentityGateway")
        return [IdentityGateway()]

    gateways = []
    for gateway_class in gateway_classes:
        try:
            gateway = gateway_class()
            logger.info(f"Using {gateway_class.__name__} for {module.name}")
            gateways.append(gateway)
        except Exception as e:
            logger.warning(
                f"Failed to instantiate {gateway_class.__name__} for {module.name}: {e}. "
                f"Skipping this gateway."
            )

    # If all gateways failed, fall back to IdentityGateway
    if not gateways:
        logger.warning(f"All gateways failed for {module.name}, falling back to IdentityGateway")
        return [IdentityGateway()]

    return gateways


def get_gateway_for_module(module: DiscoveredModule) -> Gateway:
    """Get the first gateway instance for a discovered module.

    DEPRECATED: Use get_gateways_for_module() for multiple gateway support.

    Returns the first gateway, or IdentityGateway if none specified.

    Args:
        module: DiscoveredModule to get gateway for

    Returns:
        Gateway instance (first one if multiple specified)
    """
    gateways = get_gateways_for_module(module)
    return gateways[0]


def get_gateway_class(module: DiscoveredModule) -> Optional[Type[Gateway]]:
    """Extract the first gateway class from a module if specified.

    DEPRECATED: Use module.gateway_classes for multiple gateway support.

    Args:
        module: DiscoveredModule to check

    Returns:
        First Gateway subclass if specified, None otherwise
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
