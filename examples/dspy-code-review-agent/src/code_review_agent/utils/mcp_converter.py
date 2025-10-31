"""Custom MCP tool result converter for DSPy ReAct."""

import hashlib
import base64
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    import mcp
    import mcp.client.session
import dspy


def _truncate_text(text: str, max_chars: int = 500) -> dict[str, Any]:
    """Truncate text to max_chars with head/tail preview."""
    if len(text) <= max_chars:
        return {
            "text": text,
            "truncated": False,
            "total_chars": len(text)
        }
    
    half = max_chars // 2
    return {
        "text": text[:half] + "\n[... truncated ...]\n" + text[-half:],
        "truncated": True,
        "total_chars": len(text)
    }


def _build_compact_observation(
    texts: list[dict],
    images: list[dict],
    audio: list[dict],
    blobs: list[dict]
) -> str:
    """Build observation string for the LM to read with full file contents."""
    lines = []
    
    # Status messages (TextContent without file names)
    status_messages = [t for t in texts if not t.get("name")]
    if status_messages:
        for msg in status_messages:
            lines.append(msg["preview"]["text"])
    
    # Text files - include FULL content
    text_files = [t for t in texts if t.get("name")]
    if text_files:
        for t in text_files:
            lines.append(f"\nFile: {t['name']} ({t['preview']['total_chars']} chars)")
            lines.append(f"Content:\n{t.get('full_text', t['preview']['text'])}")
    
    # Images
    if images:
        raise NotImplementedError("Images are not supported yet.")
    
    # Audio
    if audio:
        raise NotImplementedError("Audio is not supported yet.")
    
    # Binary blobs
    if blobs:
        raise NotImplementedError("Binary blobs are not supported yet.")
    
    return "\n".join(lines) if lines else "[No content]"


def _convert_mcp_tool_result(call_tool_result: "mcp.types.CallToolResult") -> dict[str, Any]:
    """Convert MCP tool result to a structured bundle optimized for DSPy ReAct.
    
    Returns a JSON-serializable bundle with:
    - observation: Compact text summary for the LM to read
    - texts: List of text content with previews
    - images: List of images (base64 or data URLs)
    - audio: List of audio (base64 + format)
    - blobs: List of binary files (metadata only, content omitted)
    """
    from mcp.types import (
        EmbeddedResource,
        TextContent,
        TextResourceContents,
        BlobResourceContents,
        ImageContent,
    )
    
    texts: list[dict[str, Any]] = []
    images: list[dict[str, Any]] = []
    audio: list[dict[str, Any]] = []
    blobs: list[dict[str, Any]] = []
    
    for content in call_tool_result.content:
        if isinstance(content, TextContent):
            # Status message or plain text
            preview = _truncate_text(content.text, max_chars=500)
            texts.append({
                "name": None,
                "mime": "text/plain",
                "preview": preview,
                "full_text": content.text,
            })
        
        elif isinstance(content, EmbeddedResource):
            resource = content.resource
            
            if isinstance(resource, TextResourceContents):
                # Text file content
                preview = _truncate_text(resource.text, max_chars=500)
                texts.append({
                    "name": str(resource.uri).split("/")[-1],
                    "mime": resource.mimeType or "text/plain",
                    "uri": str(resource.uri),
                    "preview": preview,
                    "full_text": resource.text,
                })
            
            elif isinstance(resource, BlobResourceContents):
                mime = resource.mimeType or "application/octet-stream"
                name = str(resource.uri).split("/")[-1]
                
                raise NotImplementedError("Image, Audio, orBinary content not yet supported")
        
        elif isinstance(content, ImageContent):
            raise NotImplementedError("Image content not yet supported")
        else:
            raise NotImplementedError(
                f"Content type {type(content).__name__} not yet supported. "
                f"Supported: TextContent, EmbeddedResource (text/blob), ImageContent"
            )
    
    observation = _build_compact_observation(texts, images, audio, blobs)
    
    if call_tool_result.isError:
        raise RuntimeError(f"MCP tool failed: {observation}")
    
    return {
        "ok": True,
        "observation": observation,
        "texts": texts,
        "images": images,
        "audio": audio,
        "blobs": blobs,
    }


def convert_mcp_tool(
    session: "mcp.client.session.ClientSession",
    tool: "mcp.types.Tool"
) -> "dspy.Tool":
    """Build a DSPy tool from an MCP tool with proper content handling.
    
    Returns a tool that converts MCP results to structured bundles or simple text.
    """
    import dspy
    from dspy.adapters.types.tool import convert_input_schema_to_tool_args
    
    args, arg_types, arg_desc = convert_input_schema_to_tool_args(tool.inputSchema)
    
    async def func(*args, **kwargs):
        result = await session.call_tool(tool.name, arguments=kwargs)
        bundle = _convert_mcp_tool_result(result)
        
        if (len(bundle["texts"]) == 1 and 
            not bundle["images"] and 
            not bundle["audio"] and 
            not bundle["blobs"]):
            text_item = bundle["texts"][0]
            if text_item.get("name") and text_item.get("full_text"):
                return text_item["full_text"]
            return text_item["preview"]["text"]
        
        return bundle
    
    return dspy.Tool(
        func=func,
        name=tool.name,
        desc=tool.description,
        args=args,
        arg_types=arg_types,
        arg_desc=arg_desc
    )


async def build_dspy_tools(session: "mcp.client.session.ClientSession") -> list["dspy.Tool"]:
    """Build DSPy tools from an MCP session."""
    tools = await session.list_tools()
    return [convert_mcp_tool(session, tool) for tool in tools.tools]
