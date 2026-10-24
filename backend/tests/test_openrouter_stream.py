import json

import pytest
import requests

from src import openrouter
from src.openrouter import OpenRouterError, extract_web_sources

# conftest blocks the real function in every test; keep it to test the parsing
# with requests.post replaced.
REAL_STREAM = openrouter._stream_from_openrouter


class FakeStreamResponse:
    def __init__(self, lines, status_code=200, body=None):
        self.lines = lines
        self.status_code = status_code
        self.ok = status_code < 400
        self.body = body
        self.encoding = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def json(self):
        if self.body is None:
            raise ValueError("no JSON")
        return self.body

    def iter_lines(self, decode_unicode=False):
        assert self.encoding == "utf-8"
        yield from self.lines


def data(chunk):
    return f"data: {json.dumps(chunk, ensure_ascii=False)}"


def stream_lines(monkeypatch, lines, **kwargs):
    monkeypatch.setattr(
        openrouter.requests,
        "post",
        lambda **_: FakeStreamResponse(lines, **kwargs),
    )
    return list(REAL_STREAM("https://example.test", {}, timeout=1))


def test_stream_skips_comments_and_stops_at_done(monkeypatch):
    chunks = stream_lines(
        monkeypatch,
        [
            ": OPENROUTER PROCESSING",
            "",
            data({"choices": [{"delta": {"content": "a"}}]}),
            "data: [DONE]",
            data({"choices": [{"delta": {"content": "after done"}}]}),
        ],
    )

    assert chunks == [{"choices": [{"delta": {"content": "a"}}]}]


def test_stream_keeps_polish_characters(monkeypatch):
    chunks = stream_lines(
        monkeypatch, [data({"choices": [{"delta": {"content": "Wartości własne"}}]})]
    )

    assert chunks[0]["choices"][0]["delta"]["content"] == "Wartości własne"


def test_stream_error_chunk_raises(monkeypatch):
    with pytest.raises(OpenRouterError, match="Provider overloaded"):
        stream_lines(monkeypatch, [data({"error": {"message": "Provider overloaded"}})])


def test_stream_error_status_raises_with_message(monkeypatch):
    with pytest.raises(OpenRouterError, match="429: Rate limited"):
        stream_lines(
            monkeypatch,
            [],
            status_code=429,
            body={"error": {"message": "Rate limited"}},
        )


def test_stream_connection_error_raises(monkeypatch):
    def failing_post(**_):
        raise requests.ConnectionError("no network")

    monkeypatch.setattr(openrouter.requests, "post", failing_post)

    with pytest.raises(OpenRouterError, match="no network"):
        list(REAL_STREAM("https://example.test", {}, timeout=1))


def fake_chunks(monkeypatch, deltas):
    chunks = [{"choices": [{"delta": delta}]} for delta in deltas]
    monkeypatch.setattr(
        openrouter,
        "_stream_from_openrouter",
        lambda url, payload, timeout: iter(chunks),
    )


def test_stream_query_yields_text_in_order_and_the_whole_message(monkeypatch):
    fake_chunks(monkeypatch, [{"content": "Wartości"}, {}, {"content": " własne"}])

    events = list(openrouter.stream_query_with_tools([], []))

    assert events == [
        ("delta", "Wartości"),
        ("delta", " własne"),
        ("message", {"role": "assistant", "content": "Wartości własne"}),
    ]


def test_stream_query_puts_tool_calls_together(monkeypatch):
    fake_chunks(
        monkeypatch,
        [
            {
                "tool_calls": [
                    {
                        "index": 0,
                        "id": "call_1",
                        "function": {"name": "add_topics", "arguments": '{"top'},
                    }
                ]
            },
            {"tool_calls": [{"index": 0, "function": {"arguments": 'ics": []}'}}]},
            {
                "tool_calls": [
                    {
                        "index": 1,
                        "id": "call_2",
                        "function": {"name": "rename_topic", "arguments": "{}"},
                    }
                ]
            },
        ],
    )

    *_, (kind, message) = openrouter.stream_query_with_tools([], [])

    assert kind == "message"
    assert message["tool_calls"] == [
        {
            "id": "call_1",
            "type": "function",
            "function": {"name": "add_topics", "arguments": '{"topics": []}'},
        },
        {
            "id": "call_2",
            "type": "function",
            "function": {"name": "rename_topic", "arguments": "{}"},
        },
    ]


def test_stream_query_collects_annotations(monkeypatch):
    citation = {
        "type": "url_citation",
        "url_citation": {"url": "https://doc.rust-lang.org", "title": "Rust docs"},
    }
    fake_chunks(monkeypatch, [{"content": "Text"}, {"annotations": [citation]}])

    *_, (_, message) = openrouter.stream_query_with_tools([], [])

    assert extract_web_sources(message["annotations"]) == [
        {"kind": "web", "title": "Rust docs", "url": "https://doc.rust-lang.org"}
    ]
