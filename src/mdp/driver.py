from __future__ import annotations

import os
import selectors
from codecs import getincrementaldecoder
from typing import Any

from textual._xterm_parser import XTermParser
from textual.app import App
from textual.drivers.linux_driver import LinuxDriver


class ReaderDriver(LinuxDriver):
    """Stops reading keys as soon as the reader quits.

    Textual's input thread notices a quit only between 0.1 second waits
    for input, then waits once more with nothing left to watch, which
    froze the reader for about 0.2 seconds before restoring the terminal.
    This thread also watches a pipe that `disable_input` writes to.
    """

    def __init__(
        self,
        app: App[Any],
        *,
        debug: bool = False,
        mouse: bool = True,
        size: tuple[int, int] | None = None,
    ) -> None:
        super().__init__(app, debug=debug, mouse=mouse, size=size)
        self.wake_read, self.wake_write = os.pipe()

    def disable_input(self) -> None:
        os.write(self.wake_write, b"\0")
        super().disable_input()

    def close(self) -> None:
        super().close()
        os.close(self.wake_read)
        os.close(self.wake_write)

    def resume_application_mode(self) -> None:
        # Suspending closes the driver, pipe included, but resuming starts
        # a new input thread on this same driver.
        self.wake_read, self.wake_write = os.pipe()
        super().resume_application_mode()

    def run_input_thread(self) -> None:
        parser = XTermParser()
        decode = getincrementaldecoder("utf-8")().decode
        with selectors.SelectSelector() as selector:
            selector.register(self.fileno, selectors.EVENT_READ)
            selector.register(self.wake_read, selectors.EVENT_READ)
            while not self.exit_event.is_set():
                for key, _ in selector.select(0.1):
                    data = os.read(key.fd, 4096)
                    if key.fd == self.wake_read:
                        return
                    # An empty feed tells the parser input has ended, so
                    # skip partial characters until the rest arrives.
                    if text := decode(data):
                        for event in parser.feed(text):
                            self.process_message(event)
                # Escape is only reported once no sequence follows it.
                for event in parser.tick():
                    self.process_message(event)
