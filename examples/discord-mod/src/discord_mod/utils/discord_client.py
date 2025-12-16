"""Discord API client for gateway interactions.

This is a simple async client that wraps the Discord REST API.
For production use, consider using discord.py or similar libraries.
"""

import logging
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

DISCORD_API_BASE = "https://discord.com/api/v10"


class DiscordClient:
    """Async Discord API client for moderation actions."""

    def __init__(self, token: str):
        self.token = token
        self.headers = {
            "Authorization": f"Bot {token}",
            "Content-Type": "application/json",
        }

    async def _request(
        self,
        method: str,
        endpoint: str,
        json: Optional[Dict] = None,
    ) -> Any:
        """Make an authenticated request to the Discord API."""
        url = f"{DISCORD_API_BASE}{endpoint}"
        async with httpx.AsyncClient() as client:
            response = await client.request(
                method=method,
                url=url,
                headers=self.headers,
                json=json,
            )
            if response.status_code == 204:
                return None
            response.raise_for_status()
            return response.json()

    async def get_recent_messages(
        self,
        channel_id: str,
        limit: int = 50,
        after: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch recent messages from a channel.
        
        Args:
            channel_id: The channel to fetch from
            limit: Max messages to return (1-100)
            after: Only get messages after this message ID
            
        Returns:
            List of message objects from Discord API
        """
        endpoint = f"/channels/{channel_id}/messages?limit={limit}"
        if after:
            endpoint += f"&after={after}"

        try:
            messages = await self._request("GET", endpoint)
            channel = await self.get_channel(channel_id)
            for msg in messages:
                msg["channel_name"] = channel.get("name", "unknown")
            return messages
        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to fetch messages from {channel_id}: {e}")
            return []

    async def get_channel(self, channel_id: str) -> Dict[str, Any]:
        """Get channel information."""
        try:
            return await self._request("GET", f"/channels/{channel_id}")
        except httpx.HTTPStatusError:
            return {}

    async def send_message(
        self,
        channel_id: str,
        content: str,
    ) -> Dict[str, Any]:
        """Send a message to a channel."""
        return await self._request(
            "POST",
            f"/channels/{channel_id}/messages",
            json={"content": content},
        )

    async def delete_message(
        self,
        channel_id: str,
        message_id: str,
    ) -> None:
        """Delete a message."""
        await self._request(
            "DELETE",
            f"/channels/{channel_id}/messages/{message_id}",
        )

    async def add_reaction(
        self,
        channel_id: str,
        message_id: str,
        emoji: str,
    ) -> None:
        """Add a reaction to a message."""
        import urllib.parse
        encoded_emoji = urllib.parse.quote(emoji)
        await self._request(
            "PUT",
            f"/channels/{channel_id}/messages/{message_id}/reactions/{encoded_emoji}/@me",
        )

    async def send_dm(
        self,
        user_id: str,
        content: str,
    ) -> Optional[Dict[str, Any]]:
        """Send a direct message to a user."""
        try:
            dm_channel = await self._request(
                "POST",
                "/users/@me/channels",
                json={"recipient_id": user_id},
            )
            return await self.send_message(dm_channel["id"], content)
        except httpx.HTTPStatusError as e:
            logger.warning(f"Could not DM user {user_id}: {e}")
            return None
