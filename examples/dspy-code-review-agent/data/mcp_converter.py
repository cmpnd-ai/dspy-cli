"""Scalable MCP tool result converter for DSPy.

This module converts MCP (Model Context Protocol) tool results into a format
optimized for DSPy's ReAct module, handling mixed content types while keeping
observations compact and JSON-serializable.
"""

from typing import Any, TYPE_CHECKING
import hashlib
import base64

if TYPE_CHECKING:
    import mcp
    import mcp.client.session


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
            lines.append(f"\n📄 File: {t['name']} ({t['preview']['total_chars']} chars)")
            lines.append(f"Content:\n{t.get('full_text', t['preview']['text'])}")
    
    # Images
    if images:
        lines.append(f"\n🖼️  Images ({len(images)}):")
        for img in images:
            size_kb = len(img.get("base64", "")) * 3 // 4 // 1024
            lines.append(f"  - {img['name']} ({img['mime']}, ~{size_kb}KB)")
    
    # Audio
    if audio:
        lines.append(f"\n🔊 Audio ({len(audio)}):")
        for a in audio:
            size_kb = len(a.get("base64", "")) * 3 // 4 // 1024
            lines.append(f"  - {a['name']} ({a['mime']}, ~{size_kb}KB)")
    
    # Binary blobs
    if blobs:
        lines.append(f"\n📦 Binary files ({len(blobs)}):")
        for b in blobs:
            size_kb = b.get("size", 0) // 1024
            lines.append(f"  - {b['name']} ({b['mime']}, {size_kb}KB) [content omitted]")
    
    return "\n".join(lines) if lines else "[No content]"


def _convert_mcp_tool_result(call_tool_result: "mcp.types.CallToolResult") -> dict[str, Any]:
    """Convert MCP tool result to a structured bundle optimized for DSPy ReAct.
    
    Returns a JSON-serializable bundle with:
    - observation: Compact text summary for the LM to read
    - texts: List of text content with previews
    - images: List of images (base64 or data URLs)
    - audio: List of audio (base64 + format)
    - blobs: List of binary files (metadata only, content omitted)
    
    The observation is kept small (<2KB) while full content is preserved in attachments.
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
                    "full_text": resource.text,  # Keep full text for app use
                })
            
            elif isinstance(resource, BlobResourceContents):
                mime = resource.mimeType or "application/octet-stream"
                name = str(resource.uri).split("/")[-1]
                
                if mime.startswith("image/"):
                    # Image content
                    raise NotImplementedError("Image content not yet supported")
                
                elif mime.startswith("audio/"):
                    # Audio content
                    raise NotImplementedError("Audio content not yet supported")
                
                else:
                    # Other binary content - don't include large blobs
                    blob_bytes = base64.b64decode(resource.blob)
                    blob_hash = hashlib.sha256(blob_bytes).hexdigest()
                    blobs.append({
                        "name": name,
                        "mime": mime,
                        "uri": str(resource.uri),
                        "size": len(blob_bytes),
                        "sha256": blob_hash[:16] + "...",
                        "note": "content omitted from observation",
                    })
        
        elif isinstance(content, ImageContent):
            # Direct image content
            raise NotImplementedError("Image content not yet supported")
        
        else:
            # Unknown content type
            raise NotImplementedError(
                f"Content type {type(content).__name__} not yet supported. "
                f"Supported: TextContent, EmbeddedResource (text/blob), ImageContent"
            )
    
    # Build compact observation for the LM
    observation = _build_compact_observation(texts, images, audio, blobs)
    
    # Check for errors
    if call_tool_result.isError:
        raise RuntimeError(f"MCP tool failed: {observation}")
    
    # Return structured bundle
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
    
    The returned tool function will:
    1. Call the MCP tool via the session
    2. Convert the result to a structured bundle (see _convert_mcp_tool_result)
    3. Return either:
       - The bundle dict (if multiple content types)
       - Just the text (if only one text file with no status message)
       - The observation string (if mixed content with no substantial data)
    
    This ensures ReAct gets clean, compact observations while preserving
    full content for application use.
    """
    import dspy
    from dspy.adapters.types.tool import convert_input_schema_to_tool_args
    
    args, arg_types, arg_desc = convert_input_schema_to_tool_args(tool.inputSchema)
    
    async def func(*args, **kwargs):
        result = await session.call_tool(tool.name, arguments=kwargs)
        bundle = _convert_mcp_tool_result(result)
        
        # Simplify return value when possible:
        # If there's exactly one text file and no other content, return just the text
        if (len(bundle["texts"]) == 1 and 
            not bundle["images"] and 
            not bundle["audio"] and 
            not bundle["blobs"]):
            text_item = bundle["texts"][0]
            # If it has a name (is a file), return full text
            if text_item.get("name") and text_item.get("full_text"):
                return text_item["full_text"]
            # Otherwise return the preview text (status message)
            return text_item["preview"]["text"]
        
        # Return full bundle for mixed content
        return bundle
    
    return dspy.Tool(
        func=func,
        name=tool.name,
        desc=tool.description,
        args=args,
        arg_types=arg_types,
        arg_desc=arg_desc
    )
