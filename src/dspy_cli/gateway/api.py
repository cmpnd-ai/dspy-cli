"""API Gateway for HTTP request/response transformation."""

from typing import Any, Dict, Optional, Type

from pydantic import BaseModel

from dspy_cli.gateway.base import Gateway


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
    requires_auth: bool = False

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

    def from_pipeline_output(self, output: Any) -> Any:
        """Transform pipeline output to HTTP response.
        
        Args:
            output: The normalized output dict from execute_pipeline
            
        Returns:
            The HTTP response body (will be serialized to JSON)
        """
        return output


class IdentityGateway(APIGateway):
    """Default gateway - HTTP inputs == pipeline inputs.
    
    This provides backward compatibility: modules without an explicit
    gateway attribute use this, which passes inputs/outputs unchanged.
    """
    pass
