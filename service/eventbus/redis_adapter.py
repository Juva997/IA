"""Adapter protótipo para EventBus usando Redis pub/sub (aioredis).

Este arquivo é um esboço — aioredis/redis async é opcional e depende do ambiente.
"""
try:
    import aioredis  # type: ignore
except Exception:
    aioredis = None


class RedisEventBusAdapter:
    def __init__(self, redis_url: str = "redis://localhost:6379/0", channel_prefix: str = "evt:"):
        self.redis_url = redis_url
        self.channel_prefix = channel_prefix

    async def publish(self, event: str, payload):
        if aioredis is None:
            raise RuntimeError("aioredis não está instalado — adapter protótipo")
        redis = await aioredis.create_redis_pool(self.redis_url)
        try:
            await redis.publish_json(self.channel_prefix + event, payload)
        finally:
            redis.close()
            await redis.wait_closed()

    async def subscribe(self, event: str, handler):
        """Subscribe é deixado como exercício — protótipo mostra intenção."""
        raise NotImplementedError("subscribe protótipo — implemente com aioredis.pubsub")


__all__ = ["RedisEventBusAdapter"]
