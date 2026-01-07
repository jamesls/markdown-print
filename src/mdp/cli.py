from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from rich.console import Console

from mdp.rich_markdown import LeftAlignedMarkdown

DEFAULT_CODE_THEME = "nord-darker"
DEFAULT_WIDTH = 100


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
    args = parser.parse_args(argv)

    markdown_path = Path(args.path)
    try:
        markdown_body = markdown_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        parser.error(f"File not found: {markdown_path}")
    except OSError as exc:
        parser.error(f"Failed to read {markdown_path}: {exc}")

    console = Console(width=DEFAULT_WIDTH)
    console.print(
        LeftAlignedMarkdown(
            markdown_body,
            code_theme=DEFAULT_CODE_THEME,
            hyperlinks=True,
        )
    )
    return 0
