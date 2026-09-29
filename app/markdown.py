"""User-written Markdown to sanitized HTML. Used by Preview and, later, Export."""
from __future__ import annotations

import nh3
from markdown_it import MarkdownIt

_md = MarkdownIt("commonmark")


def render_markdown(text: str) -> str:
    # http(s) only, and no relative URLs: an image must be hosted elsewhere.
    return nh3.clean(_md.render(text), url_schemes={"http", "https"},
                     url_relative="deny")
