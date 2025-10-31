import asyncio
from mcp import StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.session import ClientSession


class MCPManager:
    """Manages MCP server lifecycle with explicit start/stop methods."""
    
    def __init__(self, server_params: StdioServerParameters):
        self.server_params = server_params
        self._stdio_cm = None
        self._session_cm = None
        self.session: ClientSession | None = None
        self._started = False
        self._lock = asyncio.Lock()

    async def start(self) -> ClientSession:
        """Start the MCP server and initialize session."""
        if self._started and self.session:
            return self.session
            
        async with self._lock:
            if self._started and self.session:
                return self.session
                
            self._stdio_cm = stdio_client(self.server_params)
            read, write = await self._stdio_cm.__aenter__()
            
            self._session_cm = ClientSession(read, write)
            self.session = await self._session_cm.__aenter__()
            await self.session.initialize()
            
            self._started = True
            return self.session

    async def stop(self):
        """Stop the MCP server and cleanup resources."""
        if not self._started:
            return
            
        async with self._lock:
            if not self._started:
                return
                
            try:
                if self._session_cm:
                    await self._session_cm.__aexit__(None, None, None)
            finally:
                if self._stdio_cm:
                    await self._stdio_cm.__aexit__(None, None, None)
                self.session = None
                self._session_cm = None
                self._stdio_cm = None
                self._started = False
