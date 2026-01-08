from __future__ import annotations

import argparse
import subprocess
from collections.abc import Sequence
from pathlib import Path

from pygments.styles import get_style_by_name
from rich.align import Align
from rich.console import Console, RenderableType
from rich.pager import Pager
from rich.theme import Theme

from mdp.markdown import LeftAlignedMarkdown


class LessPager(Pager):
    """Pager that uses less with ANSI color support."""

    def show(self, content: str) -> None:
        subprocess.run(["less", "-R"], input=content, text=True)


DEFAULT_CODE_THEME = "nord-darker"
DEFAULT_WIDTH = 100
_code_background = get_style_by_name(DEFAULT_CODE_THEME).background_color
DEFAULT_CONSOLE_THEME = Theme({
    "markdown.code": f"#81a1c1 on {_code_background}",
    "markdown.hr": "#4c566a",
    "markdown.item.number": "#4c566a bold",
})


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="mdp",
        description="Render Markdown to the terminal with Rich.",
    )
    parser.add_argument(
        "path",
        metavar="PATH",
        help="Path to a Markdown file.",
    )
    parser.add_argument(
        "--page",
        action="store_true",
        help="Use a pager to display output with color support.",
    )
    parser.add_argument(
        "--center",
        action="store_true",
        help="Center the rendered markdown horizontally on the terminal.",
    )
    args = parser.parse_args(argv)

    markdown_path = Path(args.path)
    try:
        markdown_body = markdown_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        parser.error(f"File not found: {markdown_path}")
    except OSError as exc:
        parser.error(f"Failed to read {markdown_path}: {exc}")

    console = Console(
        width=None if args.center else DEFAULT_WIDTH,
        theme=DEFAULT_CONSOLE_THEME,
        force_terminal=True if args.page else None,
    )
    markdown = LeftAlignedMarkdown(
        markdown_body,
        code_theme=DEFAULT_CODE_THEME,
        hyperlinks=True,
    )
    renderable: RenderableType = markdown
    if args.center:
        renderable = Align.center(markdown, width=DEFAULT_WIDTH, pad=False)
    if args.page:
        with console.pager(pager=LessPager(), styles=True):
            console.print(renderable)
    else:
        console.print(renderable)
    return 0
