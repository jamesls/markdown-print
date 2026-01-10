from __future__ import annotations

import subprocess

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

__all__ = ["render_markdown", "LeftAlignedMarkdown"]

DEFAULT_CODE_THEME = "nord-darker"
DEFAULT_WIDTH = 100
_code_background = get_style_by_name(DEFAULT_CODE_THEME).background_color
DEFAULT_CONSOLE_THEME = Theme({
    "markdown.code": f"#81a1c1 on {_code_background}",
    "markdown.hr": "#4c566a",
    "markdown.item.number": "#4c566a bold",
})


def render_markdown(
    text: str,
    *,
    width: int = DEFAULT_WIDTH,
    center: bool = False,
    page: bool = False,
    code_theme: str = DEFAULT_CODE_THEME,
    hyperlinks: bool = True,
) -> None:
    """Render markdown text to the console.

    Args:
        text: Markdown string to render.
        width: Maximum width for rendering.
        center: Center output horizontally in terminal.
        page: Send output through a pager (less).
        code_theme: Pygments theme for code blocks.
        hyperlinks: Render clickable hyperlinks.
    """
    console = Console(
        width=None if center else width,
        theme=DEFAULT_CONSOLE_THEME,
        force_terminal=True if page else None,
    )
    markdown = LeftAlignedMarkdown(
        text,
        code_theme=code_theme,
        hyperlinks=hyperlinks,
    )
    renderable: RenderableType = markdown
    if center:
        renderable = Align.center(markdown, width=width, pad=False)
    if page:
        with console.pager(pager=LessPager(), styles=True):
            console.print(renderable)
    else:
        console.print(renderable)
