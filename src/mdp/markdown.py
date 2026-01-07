from __future__ import annotations

from typing import ClassVar

from rich import box
from rich.console import Console, ConsoleOptions, RenderResult
from rich.markdown import Heading as RichHeading
from rich.markdown import Markdown as RichMarkdown
from rich.markdown import MarkdownElement
from rich.panel import Panel
from rich.text import Text


class LeftAlignedHeading(RichHeading):
    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        text = self.text
        text.justify = "left"

        # Prepend markdown header syntax based on heading level
        level = int(self.tag[1])  # Extract number from h1, h2, etc.
        prefix = "#" * level + " "
        text = Text(prefix, style=text.style) + text

        if self.tag == "h1":
            yield Panel(text, box=box.HEAVY, style="markdown.h1.border")
            return

        if self.tag == "h2":
            yield Text("")
        yield text


class LeftAlignedMarkdown(RichMarkdown):
    elements: ClassVar[dict[str, type[MarkdownElement]]] = dict(
        RichMarkdown.elements
    )
    elements["heading_open"] = LeftAlignedHeading
