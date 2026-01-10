from __future__ import annotations

from io import StringIO

from rich.console import Console

from mdp.markdown import LeftAlignedMarkdown


def test_h1_renders_in_panel() -> None:
    output = StringIO()
    console = Console(file=output, width=40, force_terminal=False)
    console.print(LeftAlignedMarkdown("# Main Title"))

    rendered = output.getvalue()
    assert "Main Title" in rendered
    # Panel uses box characters
    assert "━" in rendered or "─" in rendered


def test_h2_has_blank_line_before() -> None:
    output = StringIO()
    console = Console(file=output, width=40, force_terminal=False)
    console.print(LeftAlignedMarkdown("## Second Level"))

    rendered = output.getvalue()
    lines = rendered.split("\n")
    heading_index = next(
        i for i, line in enumerate(lines) if "Second Level" in line
    )
    # h2 should have a blank line before it
    assert heading_index > 0
    assert lines[heading_index - 1].strip() == ""


def test_h3_renders_with_hash_prefix() -> None:
    output = StringIO()
    console = Console(file=output, width=40, force_terminal=False)
    console.print(LeftAlignedMarkdown("### Third Level"))

    rendered = output.getvalue()
    assert "### Third Level" in rendered


def test_h4_renders_with_hash_prefix() -> None:
    output = StringIO()
    console = Console(file=output, width=40, force_terminal=False)
    console.print(LeftAlignedMarkdown("#### Fourth Level"))

    rendered = output.getvalue()
    assert "#### Fourth Level" in rendered


def test_h5_renders_with_hash_prefix() -> None:
    output = StringIO()
    console = Console(file=output, width=40, force_terminal=False)
    console.print(LeftAlignedMarkdown("##### Fifth Level"))

    rendered = output.getvalue()
    assert "##### Fifth Level" in rendered


def test_h6_renders_with_hash_prefix() -> None:
    output = StringIO()
    console = Console(file=output, width=40, force_terminal=False)
    console.print(LeftAlignedMarkdown("###### Sixth Level"))

    rendered = output.getvalue()
    assert "###### Sixth Level" in rendered


def test_heading_text_is_left_justified() -> None:
    output = StringIO()
    console = Console(file=output, width=80, force_terminal=False)
    console.print(LeftAlignedMarkdown("### Left Aligned"))

    rendered = output.getvalue()
    lines = [line for line in rendered.split("\n") if "Left Aligned" in line]
    assert len(lines) > 0
    heading_line = lines[0]
    # Should start near the beginning (left-aligned), not centered
    assert heading_line.lstrip() == heading_line or heading_line.startswith(
        "###"
    )
