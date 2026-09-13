from __future__ import annotations

import json

import redis

from faraday.config import EVENTS_CHANNEL, QUEUE_KEY, REDIS_URL

_client: redis.Redis | None = None


def connection() -> redis.Redis:
    global _client
    if _client is None:
        _client = redis.Redis.from_url(REDIS_URL, decode_responses=True)
    return _client


def enqueue(job: dict) -> None:
    connection().rpush(QUEUE_KEY, json.dumps(job))


def dequeue(timeout_s: int = 5) -> dict | None:
    item = connection().blpop(QUEUE_KEY, timeout=timeout_s)
    if item is None:
        return None
    return json.loads(item[1])


def publish_event(event: dict) -> None:
    connection().publish(EVENTS_CHANNEL, json.dumps(event))
