"""Data-driven query synonyms for the compact default retrieval path.

The default install searches 777 JSON knowledge cards with plain keyword
matching (the real FTS5 engine is an optional 164 MB download). This alias
table sits in front of query tokenization so vocabulary mismatches — a user
saying "glow" while the cards say "bloom" — still retrieve the right cards.

Extend by adding entries to :data:`SYNONYMS`; each key is a lowercase query
token, each value the alternative tokens that should ALSO count as a hit for
it. Expansion is one-way (query-side only) and one level deep by design —
no transitive chains, no card-side rewriting.
"""

from __future__ import annotations

from collections.abc import Iterable

SYNONYMS: dict[str, tuple[str, ...]] = {
    # visual-vocabulary aliases
    "kaleidoscope": ("mirror", "kaleido"),
    "glow": ("bloom",),
    "mask": ("matte",),
    "warp": ("displace", "distort"),
    "blur": ("gaussian",),
    "mix": ("composite", "blend"),
    "colour": ("color",),
    # audio-vocabulary aliases
    "sound": ("audio",),
    "music": ("audio",),
    "mic": ("audio", "microphone"),
    "vj": ("audio", "reactive"),
    # particle-vocabulary aliases
    "particles": ("pop", "particle"),
    "particle": ("pop",),
}


def synonyms_for(token: str) -> tuple[str, ...]:
    """Return the alias tokens for one lowercase query token (possibly empty)."""
    return SYNONYMS.get(token, ())


def expand_query_tokens(tokens: Iterable[str]) -> list[tuple[str, ...]]:
    """Expand query tokens into variant groups.

    Each group is ``(original_token, *aliases)``; a group counts as matched
    when ANY of its variants appears in the searched text.
    """
    return [(token, *SYNONYMS.get(token, ())) for token in tokens]


__all__ = ["SYNONYMS", "expand_query_tokens", "synonyms_for"]
