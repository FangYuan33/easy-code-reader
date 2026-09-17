"""Offload file work without leaving workers using cleaned temporary paths."""

import asyncio
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path
from functools import partial


async def run_io(function, *args, **kwargs):
    task = asyncio.create_task(asyncio.to_thread(partial(function, *args, **kwargs)))
    try:
        return await asyncio.shield(task)
    except asyncio.CancelledError:
        # Threads cannot be cancelled. Wait before the caller removes its workspace.
        try:
            await task
        except Exception:
            pass
        raise


@asynccontextmanager
async def temporary_directory(root):
    directory = tempfile.TemporaryDirectory(prefix="work-", dir=root)
    try:
        yield Path(directory.name)
    finally:
        await run_io(directory.cleanup)
