"""Resource URI helpers for TD event payloads."""

from __future__ import annotations

from urllib.parse import quote, unquote


def encode_td_path(path: str) -> str:
    return quote(path, safe="")


def decode_td_path(encoded: str) -> str:
    return unquote(encoded)


def chop_uri(path: str, channel: str) -> str:
    return f"td://chop/path/{encode_td_path(path)}/channel/{quote(channel, safe='')}"


def par_uri(path: str, name: str) -> str:
    return f"td://par/path/{encode_td_path(path)}/name/{quote(name, safe='')}"


def cook_uri(path: str) -> str:
    return f"td://cook/path/{encode_td_path(path)}"


def error_uri(path: str) -> str:
    return f"td://error/path/{encode_td_path(path)}"


def top_frame_uri(path: str) -> str:
    return f"td://top/path/{encode_td_path(path)}/frame"
