from http.client import HTTPResponse
import os
import subprocess
from typing import Awaitable, Callable, Optional

MessageSender = Callable[
    [int, str, str, Optional[list[tuple[HTTPResponse, str]]]], Awaitable[None]
]


def make_dir_if_not_exist(path):
    if not os.path.exists(path):
        os.makedirs(path)

def run_migrations():
    subprocess.run(["yoyo", "apply", "-b"])
