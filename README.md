# markdown-print

A thin wrapper around [Rich's](https://github.com/Textualize/rich) markdown
renderer with opinionated defaults for terminal display. Rich does all the
actual parsing and rendering, this package just configures it with:

- Nord-darker theme for code blocks with matching inline code styling
- Left-aligned headings with visible `#` prefix markers
- H1 rendered in a panel, other headings styled normally
- Paged output via `less -R` by default (preserves ANSI colors)
- Horizontally centered content within a 100-character width
- A `render_markdown()` function for programmatic use

I found myself continually copying this around or making one-off scripts
with these defaults, so I packaged it up in a repo so I can install it
as needed.

There's intentionally no config files nor are there a lot of options, it's
meant to represent how I prefer markdown rendered in the terminal.

<p align="center">
  <img src="./docs/img/mdp-render.png", alt="Markdown rendered in terminal with mdp" width="1100">
</p>

## Installation

```sh
uv tool install markdown-print
```

## Usage

```sh
mdp path/to/file.md
```

## Development

This project requires Python 3.12 and uses
[uv](https://github.com/astral-sh/uv) to manage dependencies.

You can create a virtual environment with all the necessary dependencies
by running:

```sh
uv sync --all-extras --dev
```

This will install all necessary dependencies and install this project
in editable mode.

You can activate the venv with:

```sh
. .venv/bin/activate
```
