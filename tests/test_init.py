from __future__ import annotations

from unittest.mock import create_autospec

from rich.pager import Pager

from mdp import render_markdown


def test_render_markdown_outputs_content(capsys) -> None:
    render_markdown("# Hello\n\nWorld", page=False)

    captured = capsys.readouterr()
    assert "Hello" in captured.out
    assert "World" in captured.out


def test_render_markdown_with_custom_width(capsys) -> None:
    long_text = "This is a very long line " * 10
    render_markdown(long_text, width=40, page=False)

    captured = capsys.readouterr()
    lines = captured.out.strip().split("\n")
    assert all(len(line) <= 40 for line in lines)


def test_render_markdown_with_page_uses_provided_pager() -> None:
    mock_pager = create_autospec(Pager)

    render_markdown("# Test", page=True, pager=mock_pager)

    mock_pager.show.assert_called_once()
    call_args = mock_pager.show.call_args
    assert "Test" in call_args[0][0]


def test_render_markdown_with_code_block(capsys) -> None:
    code_markdown = "```python\nprint('hello')\n```"
    render_markdown(code_markdown, page=False)

    captured = capsys.readouterr()
    assert "print" in captured.out


def test_render_markdown_renders_bold_text(capsys) -> None:
    render_markdown("This is **bold** text", page=False)

    captured = capsys.readouterr()
    assert "bold" in captured.out


def test_render_markdown_renders_links(capsys) -> None:
    render_markdown("[Example](https://example.com)", page=False)

    captured = capsys.readouterr()
    assert "Example" in captured.out
