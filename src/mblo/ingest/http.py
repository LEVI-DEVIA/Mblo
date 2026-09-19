"""Polite HTTP fetcher: per-host delay, retries, raw snapshots on disk."""

import re
import time
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

import httpx

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128 Safari/537.36 Mblo/0.1"
)

# robots.txt on brvm.org asks for 10 s; SikaFinance has no rule, 2 s by courtesy.
HOST_DELAYS = {"www.brvm.org": 10.0, "www.sikafinance.com": 2.0}
DEFAULT_DELAY = 2.0


class RawStore:
    """Keeps a copy of every fetched page under raw_dir/YYYY-MM-DD/."""

    def __init__(self, raw_dir: str | Path):
        self.root = Path(raw_dir)

    def save(self, url: str, content: bytes, day: date | None = None) -> Path:
        day = day or date.today()
        folder = self.root / day.isoformat()
        folder.mkdir(parents=True, exist_ok=True)
        p = urlparse(url)
        name = re.sub(r"[^A-Za-z0-9._-]+", "_", (p.netloc + p.path + ("_" + p.query if p.query else "")))
        path = folder / name[:180]
        path.write_bytes(content)
        return path


class Fetcher:
    def __init__(self, store: RawStore | None = None, timeout: float = 30.0):
        self.client = httpx.Client(headers={"User-Agent": UA}, timeout=timeout, follow_redirects=True)
        self.store = store
        self._last: dict[str, float] = {}

    def _wait(self, host: str) -> None:
        delay = HOST_DELAYS.get(host, DEFAULT_DELAY)
        last = self._last.get(host)
        if last is not None:
            remaining = delay - (time.monotonic() - last)
            if remaining > 0:
                time.sleep(remaining)

    def get(self, url: str, retries: int = 3) -> bytes:
        host = urlparse(url).netloc
        last_err: Exception | None = None
        for attempt in range(retries):
            self._wait(host)
            self._last[host] = time.monotonic()
            try:
                r = self.client.get(url)
                r.raise_for_status()
                if self.store:
                    self.store.save(url, r.content)
                return r.content
            except httpx.HTTPError as e:
                last_err = e
                time.sleep(2 * (attempt + 1))
        raise RuntimeError(f"fetch failed after {retries} attempts: {url}") from last_err

    def get_text(self, url: str) -> str:
        return self.get(url).decode("utf-8", errors="replace")

    def close(self) -> None:
        self.client.close()
