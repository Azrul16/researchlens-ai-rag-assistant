import secrets
import time
from collections import defaultdict, deque

from app.core.config import get_settings


class RateLimiter:
    """Per-client development limits; use a shared gateway/Redis with multiple workers."""

    def __init__(self):
        self.events: dict[str, deque] = defaultdict(deque)

    def allowed(self, client: str):
        now = time.monotonic()
        stale = [key for key, events in self.events.items() if not events or events[-1] < now - 60]
        for key in stale:
            del self.events[key]
        events = self.events[client]
        while events and events[0] < now - 60:
            events.popleft()
        if len(events) >= get_settings().ai_requests_per_minute:
            return False
        events.append(now)
        return True


def authorized(header: str | None):
    expected = get_settings().api_token.get_secret_value()
    if not expected:
        return True
    return secrets.compare_digest(
        (header or "").encode("utf-8"), f"Bearer {expected}".encode("utf-8")
    )
