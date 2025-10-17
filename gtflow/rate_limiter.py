
import time
import threading

class TokenBucket:
    def __init__(self, rate_per_sec: float, capacity: float = None):
        self.rate = max(0.1, float(rate_per_sec))
        self.capacity = capacity or self.rate
        self.tokens = self.capacity
        self.timestamp = time.monotonic()
        self.lock = threading.Lock()

    def acquire(self, amount: float = 1.0):
        while True:
            with self.lock:
                now = time.monotonic()
                delta = now - self.timestamp
                self.timestamp = now
                self.tokens = min(self.capacity, self.tokens + delta * self.rate)
                if self.tokens >= amount:
                    self.tokens -= amount
                    return
            time.sleep(max(0.0, 1.0 / self.rate))
