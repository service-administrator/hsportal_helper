import asyncio
import threading

from fastapi import FastAPI

import main
from backend.config import get_backend_settings


def test_backend_settings_reads_hsportal_crawl_interval(monkeypatch) -> None:
    monkeypatch.setenv("HSPORTAL_CRAWL_INTERVAL_HOURS", "2.5")
    get_backend_settings.cache_clear()

    try:
        settings = get_backend_settings()
        assert settings.hsportal_crawl_interval_hours == 2.5
    finally:
        get_backend_settings.cache_clear()


def test_hsportal_crawl_loop_repeats_until_stopped(monkeypatch) -> None:
    calls = 0
    instances: list[FakeCrawler] = []

    class CountingCrawler(FakeCrawler):
        def __init__(self) -> None:
            super().__init__()
            instances.append(self)

        def ensure_program_data(self) -> None:
            nonlocal calls
            calls += 1

    monkeypatch.setattr(main, "HsportalCrawler", CountingCrawler)

    async def run_loop() -> None:
        app = FastAPI()
        app.state.hsportal_crawl_stop_event = asyncio.Event()

        task = asyncio.create_task(main.run_hsportal_crawl_loop(app, 0.000001))
        for _ in range(100):
            if calls >= 2:
                break
            await asyncio.sleep(0.01)

        app.state.hsportal_crawl_stop_event.set()
        await asyncio.wait_for(task, timeout=1)

        assert calls >= 2
        assert app.state.hsportal_crawler is None
        assert all(instance.closed for instance in instances)
        assert app.state.hsportal_crawl_status["status"] == "ready"
        assert app.state.hsportal_crawl_status["interval_hours"] == 0.000001
        assert "last_finished_at" in app.state.hsportal_crawl_status

    asyncio.run(run_loop())


class FakeCrawler:
    def __init__(self) -> None:
        self.stop_event = threading.Event()
        self.closed = False

    def ensure_program_data(self) -> None:
        pass

    def close(self) -> None:
        self.closed = True

    def stop(self) -> None:
        self.stop_event.set()
        self.close()
