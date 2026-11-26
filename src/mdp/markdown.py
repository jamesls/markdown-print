from __future__ import annotations

from itertools import count
from typing import ClassVar

from rich import box
from rich.console import Console, ConsoleOptions, RenderResult
from rich.markdown import CodeBlock as RichCodeBlock
from rich.markdown import Heading as RichHeading
from rich.markdown import Markdown as RichMarkdown
from rich.markdown import MarkdownElement
from rich.panel import Panel
from rich.segment import Segment
from rich.style import Style
from rich.styled import Styled
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


class SelectableCodeBlock(RichCodeBlock):
    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        # Mark Rich's one-column code padding so copying can omit it without
        # stripping any indentation from the code itself.
        for renderable in super().__rich_console__(console, options):
            style = Style(meta={"mdp_code": True})
            if isinstance(renderable, Segment):
                yield from Segment.apply_style([renderable], style)
            else:
                yield Styled(renderable, style)


_heading_ids = count()


class OutlinedHeading(LeftAlignedHeading):
    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        # Mark the heading's own text, not its `#` prefix, so the reader can
        # list it in the table of contents and find the row it renders on.
        # The ID tells apart headings on adjacent rows, such as in a list,
        # from one heading that wraps onto several rows.
        heading = (next(_heading_ids), int(self.tag[1]), self.text.plain)
        self.text.stylize(Style(meta={"mdp_heading": heading}))
        yield from super().__rich_console__(console, options)


class SelectableMarkdown(LeftAlignedMarkdown):
    elements: ClassVar[dict[str, type[MarkdownElement]]] = dict(
        LeftAlignedMarkdown.elements
    )
    elements["heading_open"] = OutlinedHeading
    elements["fence"] = SelectableCodeBlock
    elements["code_block"] = SelectableCodeBlock
