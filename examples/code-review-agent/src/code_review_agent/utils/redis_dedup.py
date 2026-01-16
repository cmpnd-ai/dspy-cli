"""Redis-based deduplication for webhook processing."""

import logging

logger = logging.getLogger(__name__)


class RedisDedup:
    """Upstash Redis client for request deduplication.

    Uses Redis SET NX (set-if-not-exists) with TTL for atomic lock acquisition.
    This prevents duplicate processing when multiple webhooks arrive for the
    same PR (e.g., rapid pushes, webhook retries).

    Upstash Redis uses HTTP-based API, making it ideal for serverless deployments.
    """

    def __init__(self, url: str, token: str):
        """Initialize Upstash Redis connection.

        Args:
            url: Upstash Redis REST URL (e.g., https://xxx.upstash.io)
            token: Upstash Redis REST token
        """
        from upstash_redis import Redis

        self._redis = Redis(url=url, token=token)
        logger.info("Connected to Upstash Redis")

    def try_acquire(self, key: str, ttl_seconds: int = 600) -> bool:
        """Try to acquire a lock for the given key.

        Uses Redis SET NX (set if not exists) for atomic lock acquisition.
        The lock automatically expires after ttl_seconds to prevent deadlocks
        if the process crashes.

        Args:
            key: Unique key for this operation (e.g., "owner/repo:123")
            ttl_seconds: Lock TTL in seconds (default 10 minutes)

        Returns:
            True if lock acquired (we should process), False if already locked
        """
        lock_key = f"pr-review-lock:{key}"

        # SET key value NX EX ttl - atomic set-if-not-exists with expiry
        result = self._redis.set(lock_key, "processing", nx=True, ex=ttl_seconds)

        acquired = result is not None
        if acquired:
            logger.debug(f"Acquired lock for {key}")
        else:
            logger.debug(f"Lock already held for {key}")

        return acquired

    def release(self, key: str) -> None:
        """Release the lock for the given key.

        Should be called in a finally block to ensure cleanup.

        Args:
            key: The key to release
        """
        lock_key = f"pr-review-lock:{key}"
        self._redis.delete(lock_key)
        logger.debug(f"Released lock for {key}")

    def close(self) -> None:
        """Close the Redis connection.

        For Upstash Redis (HTTP-based), this is a no-op since there's
        no persistent connection to close.
        """
        # upstash-redis uses HTTP, no persistent connection to close
        pass
