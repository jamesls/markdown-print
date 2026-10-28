from __future__ import annotations

import asyncio
import sys
from collections.abc import Callable
from pathlib import Path
from unittest.mock import Mock

import pytest
from rich.console import Console
from rich.text import Text
from textual.containers import VerticalScroll
from textual.geometry import Offset
from textual.selection import Selection
from textual.widgets import Input

from mdp import DEFAULT_CONSOLE_THEME
from mdp.markdown import SelectableMarkdown
from mdp.reader import Document, Reader, Status, copy_native, render_text


def make_reader(text: str, *, width: int = 40) -> tuple[Reader, Mock]:
    clipboard = Mock(spec=Callable[[str], bool], return_value=True)
    reader = Reader(
        SelectableMarkdown(text),
        Console(theme=DEFAULT_CONSOLE_THEME),
        clipboard,
        width=width,
    )
    return reader, clipboard


@pytest.mark.parametrize("reverse", [False, True])
def test_drag_copies_partial_lines_without_centering_spaces(
    reverse: bool,
) -> None:
    async def scenario() -> None:
        reader, clipboard = make_reader("First line  \nSecond line")
        async with reader.run_test(size=(100, 20)) as pilot:
            await pilot.pause()
            assert reader.query_one(Document).region.x == 30
            start, end = (2, 0), (6, 1)
            if reverse:
                start, end = end, start
            await pilot.mouse_down(Document, offset=start)
            await pilot.hover(Document, offset=end)
            await pilot.mouse_up(Document, offset=end)
            clipboard.assert_called_once_with("rst line\nSecond")
            await pilot.press("ctrl+c", "y")
            assert clipboard.call_count == 3
            await pilot.press("escape", "ctrl+c")
            assert clipboard.call_count == 3
            assert reader.query_one(Document).text_selection is None

    asyncio.run(scenario())


def test_drag_unicode_uses_characters_instead_of_terminal_cells() -> None:
    async def scenario() -> None:
        reader, clipboard = make_reader("A 界 café 🙂 Z")
        async with reader.run_test(size=(100, 20)) as pilot:
            await pilot.mouse_down(Document, offset=(2, 0))
            await pilot.hover(Document, offset=(12, 0))
            await pilot.mouse_up(Document, offset=(12, 0))
            clipboard.assert_called_once_with("界 café 🙂")

    asyncio.run(scenario())


def test_copy_preserves_code_indentation_and_blank_lines() -> None:
    async def scenario() -> None:
        reader, clipboard = make_reader(
            "```python\ndef f():\n    return 42\n\nprint(f())\n```"
        )
        async with reader.run_test(size=(100, 20)) as pilot:
            await pilot.pause()
            document = reader.query_one(Document)
            reader.screen.selections = {
                document: Selection(Offset(1, 1), Offset(11, 4))
            }
            await pilot.press("ctrl+c")
            clipboard.assert_called_once_with(
                "def f():\n    return 42\n\nprint(f())"
            )

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "markdown",
    [
        "- item\n\n  ```python\n  def f():\n      return 42\n  ```",
        "> quote\n>\n> ```python\n> def f():\n>     return 42\n> ```",
        (
            "- outer\n\n  - inner\n\n"
            "    ```python\n    def f():\n        return 42\n    ```"
        ),
    ],
    ids=["list", "quote", "nested-list"],
)
@pytest.mark.parametrize("start_column", [0, 2])
def test_copy_removes_layout_padding_from_nested_code(
    markdown: str, start_column: int
) -> None:
    async def scenario() -> None:
        reader, clipboard = make_reader(markdown)
        async with reader.run_test(size=(100, 20)) as pilot:
            await pilot.pause()
            rows = reader.document_text.plain.split("\n")
            first = next(i for i, row in enumerate(rows) if "def f()" in row)
            end = rows[first + 1].index("42") + 2
            document = reader.query_one(Document)
            reader.screen.selections = {
                document: Selection(
                    Offset(start_column, first), Offset(end, first + 1)
                )
            }
            await pilot.press("ctrl+c")
            clipboard.assert_called_once_with("def f():\n    return 42")

    asyncio.run(scenario())


def test_resize_reflows_text_and_clears_stale_selection() -> None:
    async def scenario() -> None:
        reader, clipboard = make_reader("word " * 50)
        async with reader.run_test(size=(100, 20)) as pilot:
            await pilot.mouse_down(Document, offset=(0, 0))
            await pilot.mouse_up(Document, offset=(4, 0))
            clipboard.assert_called_with("word")
            await pilot.resize_terminal(25, 20)
            await pilot.pause()
            document = reader.query_one(Document)
            assert reader.rendered_width == document.size.width
            assert reader.rendered_width <= 25
            assert document.text_selection is None
            assert all(
                len(line) <= 25
                for line in reader.document_text.plain.splitlines()
            )
            await pilot.mouse_down(Document, offset=(0, 0))
            await pilot.mouse_up(Document, offset=(4, 0))
            clipboard.assert_called_with("word")
            assert clipboard.call_count == 2

    asyncio.run(scenario())


def test_selection_after_scrolling_copies_visible_document_lines() -> None:
    async def scenario() -> None:
        text = "  \n".join(f"Line {i}" for i in range(100))
        reader, clipboard = make_reader(text)
        async with reader.run_test(size=(100, 20)) as pilot:
            await pilot.pause()
            await pilot.press("space")
            await pilot.pause()
            viewport = reader.query_one(VerticalScroll)
            assert viewport.scroll_y > 0
            first_line = int(viewport.scroll_y)
            left = reader.query_one(Document).region.x
            await pilot.mouse_down(offset=(left, 0))
            await pilot.mouse_up(offset=(left + 7, 1))
            clipboard.assert_called_once_with(
                f"Line {first_line}\nLine {first_line + 1}"
            )
            await pilot.press("g")
            assert viewport.scroll_y == 0
            await pilot.press("G")
            assert viewport.scroll_y == viewport.max_scroll_y

    asyncio.run(scenario())


@pytest.mark.parametrize(
    ("forward", "back"),
    [("space", "b"), ("f", "b"), ("ctrl+f", "ctrl+b")],
)
def test_page_keys_scroll_a_screen_like_less(forward: str, back: str) -> None:
    async def scenario() -> None:
        text = "  \n".join(f"Line {i}" for i in range(100))
        reader, _ = make_reader(text)
        async with reader.run_test(size=(100, 20)) as pilot:
            await pilot.pause()
            viewport = reader.query_one(VerticalScroll)
            await pilot.press(forward, forward)
            assert viewport.scroll_y == 2 * (viewport.size.height - 1)
            await pilot.press(back)
            assert viewport.scroll_y == viewport.size.height - 1

    asyncio.run(scenario())


@pytest.mark.parametrize(
    ("edge", "copies_pointer_line"),
    [("left", False), ("right", True), ("scrollbar", True)],
)
@pytest.mark.parametrize("scrolled", [False, True])
def test_drag_beside_text_selects_to_the_pointer_line(
    edge: str, copies_pointer_line: bool, scrolled: bool
) -> None:
    async def scenario() -> None:
        text = "  \n".join(f"Line {i}" for i in range(100))
        reader, clipboard = make_reader(text)
        async with reader.run_test(size=(100, 20)) as pilot:
            await pilot.pause()
            if scrolled:
                await pilot.press("space")
                await pilot.pause()
            first = int(reader.query_one(VerticalScroll).scroll_y)
            region = reader.query_one(Document).region
            x = {
                "left": region.x - 5,
                "right": region.right + 5,
                "scrollbar": reader.screen.size.width - 1,
            }[edge]
            await pilot.mouse_down(offset=(region.x, 0))
            await pilot.hover(offset=(region.x + 4, 1))
            await pilot.hover(offset=(x, 2))
            await pilot.mouse_up(offset=(x, 2))
            lines = [f"Line {first}", f"Line {first + 1}"]
            if copies_pointer_line:
                lines.append(f"Line {first + 2}")
            clipboard.assert_called_once_with("\n".join(lines))

    asyncio.run(scenario())


def test_drag_up_beside_text_selects_from_the_pointer_line_start() -> None:
    async def scenario() -> None:
        text = "  \n".join(f"Line {i}" for i in range(100))
        reader, clipboard = make_reader(text)
        async with reader.run_test(size=(100, 20)) as pilot:
            await pilot.pause()
            region = reader.query_one(Document).region
            await pilot.mouse_down(offset=(region.x + 3, 2))
            await pilot.hover(offset=(region.x + 1, 1))
            await pilot.hover(offset=(region.x - 5, 0))
            await pilot.mouse_up(offset=(region.x - 5, 0))
            clipboard.assert_called_once_with("Line 0\nLine 1\nLine")

    asyncio.run(scenario())


@pytest.mark.parametrize("search", [False, True])
def test_drag_below_viewport_stops_at_last_visible_line(search: bool) -> None:
    async def scenario() -> None:
        text = "  \n".join(f"Line {i}" for i in range(100))
        reader, clipboard = make_reader(text)
        async with reader.run_test(size=(100, 20)) as pilot:
            await pilot.pause()
            if search:
                await pilot.press("slash")
                await pilot.pause()
            visible_lines = reader.query_one(VerticalScroll).region.height
            left = reader.query_one(Document).region.x
            await pilot.mouse_down(offset=(left, 0))
            await pilot.hover(offset=(left + 4, 1))
            await pilot.hover(offset=(left + 4, 19))
            await pilot.mouse_up(offset=(left + 4, 19))
            clipboard.assert_called_once_with(
                "\n".join(f"Line {i}" for i in range(visible_lines))
            )

    asyncio.run(scenario())


@pytest.mark.parametrize("edge", ["margin", "scrollbar"])
def test_drag_outside_text_after_a_drag_does_not_copy_again(
    edge: str,
) -> None:
    async def scenario() -> None:
        text = "  \n".join(f"Line {i}" for i in range(100))
        reader, clipboard = make_reader(text)
        async with reader.run_test(size=(100, 20)) as pilot:
            await pilot.pause()
            left = reader.query_one(Document).region.x
            await pilot.mouse_down(offset=(left, 0))
            await pilot.mouse_up(offset=(left + 4, 0))
            clipboard.assert_called_once_with("Line")
            x = {
                "margin": left - 5,
                "scrollbar": reader.screen.size.width - 1,
            }[edge]
            await pilot.mouse_down(offset=(x, 1))
            await pilot.hover(offset=(left + 3, 5))
            await pilot.mouse_up(offset=(left + 3, 5))
            clipboard.assert_called_once_with("Line")
            scrolled = reader.query_one(VerticalScroll).scroll_y > 0
            assert scrolled == (edge == "scrollbar")

    asyncio.run(scenario())


def test_clipboard_fallback_sends_text_to_terminal() -> None:
    async def scenario() -> None:
        reader, clipboard = make_reader("Hello world")
        clipboard.return_value = False
        async with reader.run_test(size=(100, 20)) as pilot:
            await pilot.mouse_down(Document, offset=(0, 0))
            await pilot.mouse_up(Document, offset=(5, 0))
            assert reader.clipboard == "Hello"
            assert "Copy sent to terminal" in str(
                reader.query_one(Status).content
            )

    asyncio.run(scenario())


@pytest.mark.parametrize("native", [True, False])
def test_search_pastes_the_copied_selection(native: bool) -> None:
    async def scenario() -> None:
        reader, clipboard = make_reader("Hello world")
        clipboard.return_value = native
        async with reader.run_test(size=(100, 20)) as pilot:
            await pilot.mouse_down(Document, offset=(0, 0))
            await pilot.mouse_up(Document, offset=(5, 0))
            clipboard.assert_called_once_with("Hello")
            await pilot.press("slash", "ctrl+v")
            assert reader.query_one(Input).value == "Hello"

    asyncio.run(scenario())


def test_search_accepts_reader_shortcuts_as_text_and_finds_matches() -> None:
    async def scenario() -> None:
        text = "  \n".join(["hay"] * 30 + ["query"] + ["hay"] * 30)
        reader, clipboard = make_reader(text)
        async with reader.run_test(size=(100, 20)) as pilot:
            await pilot.press("slash", "q", "u", "e", "r", "y")
            assert reader.query_one(Input).value == "query"
            await pilot.press("enter")
            assert reader.match_line == 30
            assert reader.query_one(VerticalScroll).scroll_y == 30
            clipboard.assert_not_called()
            await pilot.press("n")
            assert reader.match_line == 30

    asyncio.run(scenario())


def test_render_text_preserves_styles_and_indentation_without_padding() -> (
    None
):
    rendered = render_text(
        Text("    indented\n\nplain", style="bold"), Console(), 40
    )
    assert rendered.plain == "    indented\n\nplain"
    assert rendered.spans


def test_copy_native_transfers_exact_utf8_text(tmp_path: Path) -> None:
    destination = tmp_path / "clipboard.txt"
    command = [
        sys.executable,
        "-c",
        (
            "import pathlib, sys; "
            "pathlib.Path(sys.argv[1]).write_bytes(sys.stdin.buffer.read())"
        ),
        str(destination),
    ]
    text = "界\n    indented\n"
    assert copy_native(text, command=command)
    assert destination.read_bytes() == text.encode("utf-8")


@pytest.mark.parametrize(
    "command", [[], ["/does/not/exist"], [sys.executable, "-c", "exit(1)"]]
)
def test_copy_native_reports_unavailable_or_failed_command(
    command: list[str],
) -> None:
    assert not copy_native("text", command=command)
