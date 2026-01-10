from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from mdp import render_markdown


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
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Use a pager to display output with color support.",
    )
    parser.add_argument(
        "--center",
        action=argparse.BooleanOptionalAction,
        default=True,
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

    render_markdown(markdown_body, center=args.center, page=args.page)
    return 0
