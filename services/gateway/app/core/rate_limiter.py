import redis.asyncio as redis
from app.core.config import get_settings
import structlog

logger = structlog.get_logger()
settings = get_settings()


class RateLimiter:
    def __init__(self):
        self.redis = redis.from_url(
            settings.REDIS_URL, encoding="utf-8", decode_responses=True
        )

    async def close(self):
        await self.redis.close()

    async def check_limit(self, key: str, limit: int, window_seconds: int) -> bool:
        """
        Check if a limit has been exceeded.
        Returns True if request is allowed, False if limit exceeded.
        """
        try:
            current = await self.redis.get(key)
            if current and int(current) >= limit:
                return False

            # Use a transaction (pipeline) to ensure atomicity
            pipe = self.redis.pipeline()
            pipe.incr(key)
            if not current:
                pipe.expire(key, window_seconds)
            await pipe.execute()

            return True
        except Exception as e:
            logger.error("Rate limiter error", error=str(e))
            # In case of Redis failure, we default to allowing traffic to avoid outage
            return True

    async def increment_and_check(
        self, key: str, amount: int, limit: int, window_seconds: int
    ) -> bool:
        """
        Increment a counter by 'amount' and check if it exceeds 'limit'.
        Used for token usage.
        Returns True if request is allowed (after increment), False if limit exceeded.
        """
        try:
            # Simple INCRBY first
            current = await self.redis.incrby(key, amount)

            # If it was a new key (or expired), set expiration
            if current == amount:
                await self.redis.expire(key, window_seconds)

            if current > limit:
                return False
            return True
        except Exception as e:
            logger.error("Rate limiter error", error=str(e))
            return True

    async def check_current_usage(self, key: str, limit: int) -> bool:
        """
        Check usage without incrementing.
        Returns True if usage < limit.
        """
        try:
            current = await self.redis.get(key)
            if current and int(current) >= limit:
                return False
            return True
        except Exception as e:
            logger.error("Rate limiter error", error=str(e))
            return True

    async def record_violation(self, key: str, window_seconds: int) -> int:
        """
        Record a violation. Returns the new violation count.
        """
        try:
            count = await self.redis.incr(key)
            if count == 1:
                await self.redis.expire(key, window_seconds)
            return count
        except Exception as e:
            logger.error("Rate limiter error", error=str(e))
            return 0
