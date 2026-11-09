"""Limitation de debit par IP (fenetre glissante en memoire, par instance Cloud Run)."""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque


class RateLimiter:
    def __init__(self, max_per_minute: int, clock=time.monotonic) -> None:
        self.max = max_per_minute
        self._clock = clock
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, ip: str) -> float | None:
        """None si autorise ; sinon le nombre de secondes avant de pouvoir reessayer."""
        if self.max <= 0:
            return None
        now = self._clock()
        with self._lock:
            q = self._hits[ip]
            while q and now - q[0] >= 60:
                q.popleft()
            if len(q) >= self.max:
                return max(1.0, 60 - (now - q[0]))
            q.append(now)
            if len(self._hits) > 10000:  # evite une croissance sans borne
                for k in [k for k, v in self._hits.items() if not v or now - v[-1] >= 60]:
                    del self._hits[k]
        return None
