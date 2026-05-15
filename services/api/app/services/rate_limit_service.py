import time
from dataclasses import dataclass


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    remaining: int
    retry_after_seconds: int


class InMemoryRateLimiter:
    def __init__(self) -> None:
        self._windows: dict[str, tuple[float, int]] = {}

    async def check(self, key: str, limit: int, window_seconds: int = 60) -> RateLimitResult:
        now = time.time()
        window_start, count = self._windows.get(key, (now, 0))

        if now - window_start >= window_seconds:
            window_start = now
            count = 0

        if count >= limit:
            retry_after = max(1, int(window_seconds - (now - window_start)))
            return RateLimitResult(
                allowed=False,
                remaining=0,
                retry_after_seconds=retry_after,
            )

        count += 1
        self._windows[key] = (window_start, count)
        return RateLimitResult(
            allowed=True,
            remaining=max(0, limit - count),
            retry_after_seconds=0,
        )

    def reset(self) -> None:
        self._windows.clear()
