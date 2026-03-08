from __future__ import annotations

import asyncio
from collections.abc import Coroutine, Generator
from concurrent.futures import Future
from contextlib import contextmanager

import pytest

from src.services.provider_keys import batch_delete_task as taskmod


@contextmanager
def _fake_db_context() -> Generator[object, None, None]:
    yield object()


async def _fake_get_redis_client(*, require_redis: bool = False) -> object:
    _ = require_redis
    return object()


async def _noop_delete_side_effects(**_kwargs: object) -> None:
    return None


@pytest.mark.asyncio
async def test_run_batch_delete_waits_for_progress_updates_before_completion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    release_progress = asyncio.Event()
    updates: list[dict[str, object]] = []

    async def fake_update_task_field(
        task_id: str,
        r: object | None = None,
        **fields: object,
    ) -> None:
        _ = task_id, r
        updates.append(dict(fields))

    def fake_sync_delete(
        provider_id: str,
        key_ids: list[str],
        progress_callback: object | None = None,
    ) -> int:
        _ = provider_id, key_ids
        assert callable(progress_callback)
        progress_callback(1)
        return 1

    def fake_run_coroutine_threadsafe(
        coro: Coroutine[object, object, object],
        loop: asyncio.AbstractEventLoop,
    ) -> Future[object]:
        future: Future[object] = Future()

        async def runner() -> None:
            await release_progress.wait()
            try:
                result = await coro
            except Exception as exc:
                future.set_exception(exc)
            else:
                future.set_result(result)

        loop.call_soon_threadsafe(lambda: asyncio.create_task(runner()))
        return future

    monkeypatch.setattr(taskmod, "get_redis_client", _fake_get_redis_client)
    monkeypatch.setattr(taskmod, "_update_task_field", fake_update_task_field)
    monkeypatch.setattr(taskmod, "_sync_delete", fake_sync_delete)
    monkeypatch.setattr(taskmod.asyncio, "run_coroutine_threadsafe", fake_run_coroutine_threadsafe)
    monkeypatch.setattr("src.database.get_db_context", _fake_db_context)
    monkeypatch.setattr(
        "src.services.provider_keys.key_side_effects.run_delete_key_side_effects",
        _noop_delete_side_effects,
    )

    task = asyncio.create_task(taskmod._run_batch_delete("task-1", "provider-1", ["key-1"]))

    await asyncio.sleep(0.05)

    assert not task.done()
    assert updates == [{"status": taskmod.STATUS_RUNNING}]

    release_progress.set()
    await task

    assert updates == [
        {"status": taskmod.STATUS_RUNNING},
        {"deleted": 1},
        {
            "status": taskmod.STATUS_COMPLETED,
            "deleted": 1,
            "message": "1 keys deleted",
        },
    ]
