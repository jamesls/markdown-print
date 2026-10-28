from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from collections.abc import Callable
from functools import partial
from typing import ClassVar

from rich.console import Console, RenderableType
from rich.style import Style
from rich.text import Text
from textual import events
from textual.app import App, ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import VerticalScroll
from textual.driver import Driver
from textual.geometry import Offset
from textual.message import Message
from textual.reactive import var
from textual.screen import Screen
from textual.selection import Selection
from textual.widget import Widget
from textual.widgets import Input, Static


def clipboard_command() -> list[str]:
    """Find a local clipboard writer; remote sessions use terminal copying."""
    if os.environ.get("SSH_CONNECTION") or os.environ.get("SSH_TTY"):
        return []
    candidates: list[list[str]] = []
    if sys.platform == "darwin":
        candidates.append(["pbcopy"])
    if os.environ.get("WAYLAND_DISPLAY"):
        candidates.append(["wl-copy"])
    if os.environ.get("DISPLAY"):
        candidates.extend([
            ["xclip", "-selection", "clipboard"],
            ["xsel", "--clipboard", "--input"],
        ])
    for command in candidates:
        executable = shutil.which(command[0])
        if executable:
            return [executable, *command[1:]]
    return []


def copy_native(text: str, *, command: list[str]) -> bool:
    """Return whether a native clipboard command accepted the text."""
    if not command:
        return False
    try:
        result = subprocess.run(
            command,
            input=text.encode("utf-8"),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=2,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def render_text(
    renderable: RenderableType, console: Console, width: int
) -> Text:
    """Render styled lines before the reader applies its centering layout."""
    lines = console.render_lines(
        renderable, console.options.update(width=width), pad=False
    )
    result = Text()
    for index, segments in enumerate(lines):
        if index:
            result.append("\n")
        line = Text()
        for segment in segments:
            if not segment.control:
                line.append(segment.text, segment.style)
        result.append_text(line)
    return result


def code_indent(line: Text) -> int:
    """Return the column where code begins, or 0 outside a code block.

    Code blocks nested in lists or quotes follow that layout's padding, so
    the code starts after the enclosing padding and Rich's one-column code
    padding rather than at a fixed column.
    """
    starts = [
        start
        for start, _, style in line.spans
        if isinstance(style, Style) and style.meta.get("mdp_code")
    ]
    return min(starts) + 1 if starts else 0


class Document(Static):
    """Selectable rendered text; the surrounding layout owns the margin."""

    class Resized(Message):
        """The text needs to be rendered at its new available width."""

    def on_resize(self, event: events.Resize) -> None:
        self.post_message(self.Resized())

    def get_selection(self, selection: Selection) -> tuple[str, str] | None:
        result = super().get_selection(selection)
        if result is None:
            return None
        text, ending = result
        lines = text.split("\n")
        content = self.content
        if isinstance(content, Text):
            source_lines = content.split("\n", allow_blank=True)
            first_row = selection.start.y if selection.start else 0
            first_column = selection.start.x if selection.start else 0
            for index, line in enumerate(lines):
                column = first_column if index == 0 else 0
                indent = code_indent(source_lines[first_row + index])
                lines[index] = line[max(0, indent - column) :]
        return "\n".join(line.rstrip() for line in lines), ending

    def nearest_offset(self, x: int, y: int, start: Offset) -> Offset:
        """Return the visible text position closest to a screen position.

        Positions beside a line resolve to its start or end, and positions
        past the visible lines resolve to the nearest visible line, so a
        drag never reaches text scrolled out of view. `start` is where the
        drag began, which decides how a drag stops before a line.
        """
        lines = str(self.content).split("\n")
        region = self.content_region
        visible = self.screen.find_widget(self).visible_region
        row = min(max(y, visible.y), visible.bottom - 1) - region.y
        row = min(row, len(lines) - 1)
        before = y < visible.y or (y < visible.bottom and x < region.x)
        if not before:
            return Offset(len(lines[row]), row)
        if row > start.y:
            # Textual selects the character under the end of a drag, so
            # stop at the end of the line above instead of this row's start.
            return Offset(len(lines[row - 1]), row - 1)
        return Offset(0, row)


class Status(Static):
    ALLOW_SELECT = False


class ReaderScreen(Screen[None]):
    """Keeps document drags on the pointer's row when it leaves the text.

    Only releases that end a document drag report a text selection.
    """

    drag_start: var[Offset | None] = var(None)

    def _forward_event(self, event: events.Event) -> None:
        # Textual no longer publishes `text_selection_started_signal`, so
        # note where a press lands before the screen starts selecting.
        if isinstance(event, events.MouseDown) and not event.is_forwarded:
            widget, offset = super().get_widget_and_offset_at(event.x, event.y)
            self.drag_start = offset if isinstance(widget, Document) else None
        super()._forward_event(event)

    def on_text_selected(self, event: events.TextSelected) -> None:
        # Textual reports every mouse release, including scrollbar and
        # margin drags that leave an earlier selection in place, which
        # would copy it again over whatever the clipboard now holds.
        if self.drag_start is None:
            event.stop()
        self.drag_start = None

    def get_widget_and_offset_at(
        self, x: int, y: int
    ) -> tuple[Widget | None, Offset | None]:
        widget, offset = super().get_widget_and_offset_at(x, y)
        if self.drag_start is None or (
            isinstance(widget, Document) and offset is not None
        ):
            return widget, offset
        # Textual extends drags that leave the text to the bottom of the
        # whole document, which would copy lines the reader never saw.
        document = self.query_one(Document)
        return document, document.nearest_offset(x, y, self.drag_start)


class Reader(App[None]):
    """A centered reader with mouse selection and clipboard support."""

    ENABLE_COMMAND_PALETTE = False
    CSS = """
    Screen { background: ansi_default; color: ansi_default; }
    #viewport { align-horizontal: center; scrollbar-size: 1 1; }
    #document { width: 100%; height: auto; }
    #status { dock: bottom; height: 1; color: ansi_default; text-style: dim; }
    #search { dock: bottom; display: none; height: 3; }
    """
    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("q", "quit", "Quit"),
        Binding("ctrl+c", "copy_selection", "Copy", priority=True),
        Binding("y", "copy_selection", "Copy", show=False),
        Binding("escape", "cancel", "Clear", priority=True),
        Binding("j,down", "move(1)", show=False),
        Binding("k,up", "move(-1)", show=False),
        Binding("space,f,ctrl+f,pagedown", "page(1)", show=False),
        Binding("b,ctrl+b,pageup", "page(-1)", show=False),
        Binding("g,home", "edge(False)", show=False),
        Binding("G,end", "edge(True)", show=False),
        Binding("slash", "search", "Search"),
        Binding("n", "next_match(1)", show=False),
        Binding("N", "next_match(-1)", show=False),
    ]

    def __init__(
        self,
        renderable: RenderableType,
        render_console: Console,
        clipboard_writer: Callable[[str], bool],
        *,
        width: int = 100,
        center: bool = True,
        stats: str = "",
    ) -> None:
        super().__init__(ansi_color=True)
        # Preserve terminal defaults instead of mapping them to theme RGB.
        self.theme = "ansi-dark"
        self.renderable = renderable
        self.render_console = render_console
        self.clipboard_writer = clipboard_writer
        self.document_width = width
        self.center = center
        self.stats = stats
        self.document_text = Text()
        self.rendered_width = 0
        self.search_term = ""
        self.match_line = -1
        self.copied_text = ""

    @property
    def clipboard(self) -> str:
        # The search box pastes from here, but Textual only records text
        # copied through OSC 52, not text copied with a native tool.
        return self.copied_text

    def copy_to_clipboard(self, text: str) -> None:
        self.copied_text = text
        super().copy_to_clipboard(text)

    def get_driver_class(self) -> type[Driver]:
        driver_class = super().get_driver_class()
        # Textual's Unix driver needs termios, which Windows doesn't have.
        if sys.platform != "win32":
            from textual.drivers.linux_driver import LinuxDriver

            from mdp.driver import ReaderDriver

            if driver_class is LinuxDriver:
                return ReaderDriver
        return driver_class

    def get_default_screen(self) -> Screen[None]:
        return ReaderScreen(id="_default")

    def compose(self) -> ComposeResult:
        yield Status(id="status")
        yield Input(
            placeholder="Search (Enter to find, Esc to close)", id="search"
        )
        with VerticalScroll(id="viewport"):
            yield Document(id="document")

    def on_mount(self) -> None:
        self.query_one("#viewport").styles.align_horizontal = (
            "center" if self.center else "left"
        )
        self.query_one("#document").styles.max_width = self.document_width
        self.query_one("#viewport").focus()
        self.call_after_refresh(self.refresh_document)
        self.show_status()

    def on_resize(self, event: events.Resize) -> None:
        self.call_after_refresh(self.refresh_document)

    def on_document_resized(self, event: Document.Resized) -> None:
        self.call_after_refresh(self.refresh_document)

    def refresh_document(self) -> None:
        document = self.query_one(Document)
        width = max(1, min(self.document_width, document.size.width))
        if width == self.rendered_width:
            return
        self.screen.clear_selection()
        self.rendered_width = width
        self.document_text = render_text(
            self.renderable, self.render_console, width
        )
        document.update(self.document_text)

    def show_status(self, message: str = "") -> None:
        hint = message or "Drag to copy | Ctrl+C/y copy | / search | q quit"
        self.query_one("#status", Status).update(f"{self.stats} | {hint}")

    def on_text_selected(self, event: events.TextSelected) -> None:
        self.action_copy_selection()

    def action_copy_selection(self) -> None:
        # Copy only the document, never the search field or status bar.
        document = self.query_one(Document)
        selection = document.text_selection
        if selection is None:
            return
        result = document.get_selection(selection)
        if result is None or not result[0]:
            return
        text = result[0]
        if self.clipboard_writer(text):
            self.copied_text = text
            self.show_status("Copied selection | Esc clears | q quit")
        else:
            self.copy_to_clipboard(text)
            self.show_status(
                "Copy sent to terminal (requires OSC 52) | q quit"
            )

    def action_cancel(self) -> None:
        self.screen.clear_selection()
        self.query_one(Document).update(self.document_text)
        self.query_one("#search", Input).display = False
        self.query_one("#viewport").focus()
        self.show_status()

    def action_move(self, amount: int) -> None:
        self.query_one("#viewport", VerticalScroll).scroll_relative(
            y=amount, animate=False
        )

    def action_page(self, direction: int) -> None:
        viewport = self.query_one("#viewport", VerticalScroll)
        viewport.scroll_relative(
            y=direction * max(1, viewport.size.height - 1), animate=False
        )

    def action_edge(self, bottom: bool) -> None:
        viewport = self.query_one("#viewport", VerticalScroll)
        viewport.scroll_to(
            y=viewport.max_scroll_y if bottom else 0, animate=False
        )

    def action_search(self) -> None:
        search = self.query_one("#search", Input)
        search.display = True
        search.focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.search_term = event.value
        self.match_line = -1
        self.action_cancel()
        self.action_next_match(1)

    def action_next_match(self, direction: int) -> None:
        if not self.search_term:
            return
        lines = self.document_text.plain.split("\n")
        for step in range(1, len(lines) + 1):
            index = (self.match_line + direction * step) % len(lines)
            if self.search_term.casefold() in lines[index].casefold():
                self.match_line = index
                self.query_one("#viewport", VerticalScroll).scroll_to(
                    y=index, animate=False
                )
                highlighted = self.document_text.copy()
                highlighted.highlight_regex(
                    "(?i)" + re.escape(self.search_term),
                    "reverse",
                )
                self.query_one(Document).update(highlighted)
                self.show_status("Match | n next | N previous | / search")
                return
        self.show_status("No matches | / search | q quit")


def show_reader(
    renderable: RenderableType,
    console: Console,
    *,
    width: int,
    center: bool,
    stats: str,
) -> None:
    reader = Reader(
        renderable,
        console,
        partial(copy_native, command=clipboard_command()),
        width=width,
        center=center,
        stats=stats,
    )
    reader.run()
