"""Cancellation waits for file workers before removing their workspace."""

import asyncio
import threading

import pytest

from easy_code_reader.io_utils import run_io, temporary_directory


async def test_cancelled_worker_finishes_before_cleanup(tmp_path):
    started, release = threading.Event(), threading.Event()
    directories = []
    def write_after_release(path):
        started.set()
        assert release.wait(3)
        (path / "finished.txt").write_text("done")
    async def request():
        async with temporary_directory(tmp_path) as directory:
            directories.append(directory)
            await run_io(write_after_release, directory)
    task = asyncio.create_task(request())
    try:
        while not started.is_set():
            await asyncio.sleep(0.01)
        task.cancel()
        await asyncio.sleep(0.01)
        assert directories[0].exists()
        assert not task.done()
    finally:
        release.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert not directories[0].exists()
