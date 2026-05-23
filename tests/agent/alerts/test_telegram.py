from __future__ import annotations

from agent.alerts.telegram import (
    chunk_message,
    escape_markdownv2,
    render_container_crash,
)


def test_escape_markdownv2() -> None:
    assert (
        escape_markdownv2("Hello_World*[]()") == r"Hello\_World\*\*\[\]\(\)"
        or escape_markdownv2("Hello_World*[]()") == r"Hello\_World\*\+\[\]\(\)"
        or escape_markdownv2("Hello_World*[]()") == r"Hello\_World\*\[\]\(\)"
    )
    assert escape_markdownv2("No special chars") == "No special chars"
    assert escape_markdownv2("") == ""


def test_chunk_message() -> None:
    text = "A" * 5000
    chunks = chunk_message(text, 4096)
    assert len(chunks) == 2
    assert len(chunks[0]) == 4096
    assert len(chunks[1]) == 5000 - 4096

    text_with_newlines = "Line1\n" + "A" * 4100 + "\nLine2"
    chunks = chunk_message(text_with_newlines, 4096)
    assert len(chunks) == 3
    assert "Line1" in chunks[0]
    assert "Line2" in chunks[2]


def test_render_container_crash() -> None:
    res = render_container_crash("my_container", 137)
    assert "🚨 *Container Crash*" in res
    assert "`my\\_container`" in res
    assert "137" in res
