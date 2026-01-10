from __future__ import annotations

from io import StringIO
from pathlib import Path

import pytest
from rich.console import Console

from mdp.cli import main
from mdp.markdown import LeftAlignedMarkdown


def test_main_renders_markdown_to_stdout(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    markdown_file = tmp_path / "sample.md"
    markdown_file.write_text("# Title\n\nHello **world**\n", encoding="utf-8")

    exit_code = main([str(markdown_file), "--no-page"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Title" in captured.out
    assert "Hello world" in captured.out


def test_main_with_missing_file_exits_with_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    missing_file = tmp_path / "missing.md"

    with pytest.raises(SystemExit) as exc_info:
        main([str(missing_file)])

    assert exc_info.value.code == 2
    captured = capsys.readouterr()
    assert "File not found" in captured.err


def test_markdown_headings_render_left_aligned() -> None:
    output = StringIO()
    console = Console(file=output, width=20, force_terminal=False)
    console.print(LeftAlignedMarkdown("### Hello"))

    rendered = output.getvalue().splitlines()
    heading_line = next(line for line in rendered if "Hello" in line)
    assert heading_line.startswith("### Hello")


def test_main_with_no_page_flag(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    markdown_file = tmp_path / "sample.md"
    markdown_file.write_text("# Title\n\nContent\n", encoding="utf-8")

    exit_code = main([str(markdown_file), "--no-page"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Title" in captured.out


def test_main_with_no_center_flag(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    markdown_file = tmp_path / "sample.md"
    markdown_file.write_text("# Title\n\nContent\n", encoding="utf-8")

    exit_code = main([str(markdown_file), "--no-center", "--no-page"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Title" in captured.out


def test_main_with_both_no_flags(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    markdown_file = tmp_path / "sample.md"
    markdown_file.write_text("**Bold** text\n", encoding="utf-8")

    exit_code = main([str(markdown_file), "--no-page", "--no-center"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Bold" in captured.out
