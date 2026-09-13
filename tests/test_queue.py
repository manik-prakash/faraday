"""queue.connection() should reuse a single Redis client instead of one per call."""

from __future__ import annotations

from faraday import queue as queue_mod


class _FakeRedis:
    pass


def test_connection_is_cached_across_calls(monkeypatch) -> None:
    created = []

    def _fake_from_url(url, decode_responses=True):
        client = _FakeRedis()
        created.append(client)
        return client

    monkeypatch.setattr(queue_mod, "_client", None, raising=False)
    monkeypatch.setattr(queue_mod.redis.Redis, "from_url", staticmethod(_fake_from_url))

    first = queue_mod.connection()
    second = queue_mod.connection()

    assert first is second
    assert len(created) == 1
