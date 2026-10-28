from __future__ import annotations

import asyncio
import os
import select
import threading
import time
from collections.abc import Callable, Iterator
from unittest.mock import Mock

import pytest

# Textual's Unix driver needs termios, which Windows doesn't have.
pytest.importorskip("termios")

from rich.console import Console
from textual import events
from textual.message import Message

from mdp import DEFAULT_CONSOLE_THEME
from mdp.driver import ReaderDriver
from mdp.markdown import SelectableMarkdown
from mdp.reader import Reader


class KeyRecordingDriver(ReaderDriver):
    def __init__(self, reader: Reader) -> None:
        super().__init__(reader, mouse=False)
        self.keys: list[str] = []

    def process_message(self, message: Message) -> None:
        if isinstance(message, events.Key):
            self.keys.append(message.key)


@pytest.fixture
def reader() -> Reader:
    clipboard = Mock(spec=Callable[[str], bool], return_value=True)
    return Reader(
        SelectableMarkdown("text"),
        Console(theme=DEFAULT_CONSOLE_THEME),
        clipboard,
    )


@pytest.fixture
def runner() -> Iterator[asyncio.Runner]:
    with asyncio.Runner() as runner:
        yield runner


@pytest.fixture
def input_pipe() -> Iterator[tuple[int, int]]:
    read_end, write_end = os.pipe()
    try:
        yield read_end, write_end
    finally:
        os.close(read_end)
        os.close(write_end)


@pytest.fixture
def driver(
    reader: Reader,
    runner: asyncio.Runner,
    input_pipe: tuple[int, int],
) -> Iterator[KeyRecordingDriver]:
    async def create_driver() -> KeyRecordingDriver:
        driver = KeyRecordingDriver(reader)
        read_end, _ = input_pipe
        driver.fileno = read_end
        return driver

    driver = runner.run(create_driver())
    try:
        yield driver
    finally:
        driver.close()


@pytest.fixture
def input_thread(driver: KeyRecordingDriver) -> Iterator[threading.Thread]:
    thread = threading.Thread(target=driver.run_input_thread, daemon=True)
    thread.start()
    try:
        yield thread
    finally:
        if thread.is_alive():
            driver.disable_input()
            thread.join(timeout=5)
        assert not thread.is_alive()


# Application mode writes escape codes straight to the real stderr.
@pytest.fixture
def application_driver(
    driver: KeyRecordingDriver,
    runner: asyncio.Runner,
    capfd: pytest.CaptureFixture[str],
) -> Iterator[KeyRecordingDriver]:
    async def start_driver() -> None:
        driver.start_application_mode()

    try:
        runner.run(start_driver())
        yield driver
    finally:
        driver.stop_application_mode()


def test_reader_driver_stops_reading_keys_once_input_is_disabled(
    reader: Reader,
    driver: KeyRecordingDriver,
    input_pipe: tuple[int, int],
    input_thread: threading.Thread,
) -> None:
    assert reader.driver_class is ReaderDriver
    read_end, write_end = input_pipe

    def send(data: bytes, count: int) -> None:
        # Wait until the thread reads the data so each write is a
        # separate read, then for the keys it should produce.
        os.write(write_end, data)
        deadline = time.monotonic() + 5
        while (
            select.select([read_end], [], [], 0)[0] or len(driver.keys) < count
        ):
            assert time.monotonic() < deadline
            time.sleep(0.001)

    character = "é".encode()
    send(character[:1], 0)
    send(character[1:] + b"q", 2)
    send(b"\x1b", 3)
    assert driver.keys == ["é", "q", "escape"]
    driver.disable_input()
    input_thread.join(timeout=5)
    # Textual clears its exit flag again right away, so the thread
    # can only have stopped because the wake pipe ended its wait.
    assert not input_thread.is_alive()
    assert not driver.exit_event.is_set()


def test_reader_driver_reads_keys_after_suspend_and_resume(
    application_driver: KeyRecordingDriver,
    runner: asyncio.Runner,
    input_pipe: tuple[int, int],
) -> None:
    async def scenario() -> None:
        # Suspending closes the driver, and resuming restarts application
        # mode on that same driver, as Ctrl+Z and fg do.
        application_driver.suspend_application_mode()
        application_driver.resume_application_mode()
        _, write_end = input_pipe
        os.write(write_end, b"q")
        deadline = time.monotonic() + 5
        while not application_driver.keys:
            assert time.monotonic() < deadline
            await asyncio.sleep(0.001)
        assert application_driver.keys == ["q"]

    runner.run(scenario())
