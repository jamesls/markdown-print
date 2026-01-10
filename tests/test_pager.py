from __future__ import annotations

from collections.abc import Callable
from unittest.mock import Mock, create_autospec

from mdp import LessPager


def test_less_pager_calls_runner_with_correct_args() -> None:
    mock_runner = create_autospec(Callable[[list[str], str], None])
    pager = LessPager(runner=mock_runner)

    pager.show("test content")

    mock_runner.assert_called_once_with(["less", "-R"], "test content")


def test_less_pager_passes_content_to_runner() -> None:
    captured_content: list[str] = []

    def capture_runner(_args: list[str], content: str) -> None:
        captured_content.append(content)

    pager = LessPager(runner=capture_runner)
    pager.show("# Markdown\n\nSome text here.")

    assert captured_content == ["# Markdown\n\nSome text here."]


def test_less_pager_with_multiline_content() -> None:
    mock_runner = Mock()
    pager = LessPager(runner=mock_runner)
    multiline = "Line 1\nLine 2\nLine 3"

    pager.show(multiline)

    mock_runner.assert_called_once_with(["less", "-R"], multiline)
