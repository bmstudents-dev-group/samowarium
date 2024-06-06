from http.client import HTTPResponse
import os
from typing import Awaitable, Callable, Optional
import asyncio

MessageSender = Callable[
    [int, str, str, Optional[list[tuple[HTTPResponse, str]]]], Awaitable[None]
]


def make_dir_if_not_exist(path):
    if not os.path.exists(path):
        os.makedirs(path)


async def retry_on_exception(
    func: Awaitable[Callable[[], None]],
    delay: int,
    on_success: Callable[[], None],
    on_failure: Callable[[Exception], None],
    retry_count: int | None = None,
) -> bool:
    retries = 0
    is_executed = False
    while not is_executed and retries < retry_count:
        try:
            await func()
            is_executed = True
            on_success()
            return True
        except Exception as e:
            on_failure(e)
            retries += 1
            await asyncio.sleep(delay)
    return False
