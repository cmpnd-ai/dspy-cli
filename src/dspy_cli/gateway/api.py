"""API Gateway for HTTP request/response transformation."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Dict, Optional, Type

from pydantic import BaseModel

from dspy_cli.gateway.base import Gateway
from dspy_cli.gateway.types import PipelineOutput

if TYPE_CHECKING:
    from fastapi import FastAPI


class APIGateway(Gateway):
    """Gateway for HTTP request/response transformation.
    
    Use this when you need to:
    - Transform HTTP request bodies before passing to the pipeline
    - Transform pipeline outputs before returning as HTTP response
    - Customize the HTTP endpoint path or method
    - Add authentication requirements
    
    Example:
        class MyGateway(APIGateway):
            path = "/api/v2/analyze"
            
            def to_pipeline_inputs(self, request):
                # Transform webhook payload to pipeline format
                return {"text": request["data"]["content"]}
            
            def from_pipeline_output(self, output):
                # Wrap output for API consumers
                return {"status": "success", "result": output}
    """

    request_model: Optional[Type[BaseModel]] = None
    response_model: Optional[Type[BaseModel]] = None
    path: Optional[str] = None
    method: str = "POST"
    requires_auth: bool = True

    def to_pipeline_inputs(self, request: Any) -> Dict[str, Any]:
        """Transform HTTP request to forward() kwargs.
        
        Args:
            request: The HTTP request body (Pydantic model or dict)
            
        Returns:
            Dictionary of kwargs to pass to the DSPy module's forward()
        """
        if isinstance(request, BaseModel):
            return request.model_dump()
        return dict(request) if request else {}

    def from_pipeline_output(self, output: PipelineOutput) -> Any:
        """Transform pipeline output to HTTP response.
        
        Args:
            output: The normalized output dict from execute_pipeline
            
        Returns:
            The HTTP response body (will be serialized to JSON)
        """
        return output

    def configure_route(
        self,
        app: FastAPI,
        route_path: str,
        endpoint: Callable[..., Any],
        response_model: Optional[Type[Any]] = None,
    ) -> None:
        """Configure the FastAPI route for this gateway.
        
        Override to customize route registration, add dependencies,
        custom responses, tags, rate limiting, etc.
        
        Args:
            app: The FastAPI application instance
            route_path: The URL path for this endpoint
            endpoint: The async function to handle requests
            response_model: Optional Pydantic model for response validation
        """
        app.add_api_route(
            route_path,
            endpoint,
            methods=[self.method],
            response_model=response_model,
        )


class IdentityGateway(APIGateway):
    """Default gateway - HTTP inputs == pipeline inputs.
    
    This provides backward compatibility: modules without an explicit
    gateway attribute use this, which passes inputs/outputs unchanged.
    """
    pass
