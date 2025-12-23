"""Gateway abstractions for HTTP and scheduled pipeline execution.

Gateways separate HTTP endpoint concerns from DSPy pipeline logic:
- APIGateway: Transform HTTP requests to pipeline inputs and outputs
- CronGateway: Load data from external sources on a schedule
- IdentityGateway: Default pass-through (backward compatible)
"""

from dspy_cli.gateway.api import APIGateway, IdentityGateway
from dspy_cli.gateway.base import Gateway
from dspy_cli.gateway.cron import CronGateway
from dspy_cli.gateway.types import PipelineInputs, PipelineOutput

__all__ = [
    "Gateway",
    "APIGateway",
    "IdentityGateway",
    "CronGateway",
    "PipelineOutput",
    "PipelineInputs",
]
