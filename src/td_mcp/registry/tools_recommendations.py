"""Official-recommendation tools — 3-card-search surface over the knowledge corpus.

Part of the v1.5.0 Phase 2 module split. See
``src/td_mcp/registry/__init__.py`` for the intentional-cycle pattern.

Tools in this module:
    td_recommend_official_component  — palette / operator suggestions
                                        for a goal
    td_find_official_example         — snippets + palette examples
                                        matching a query
    td_explain_better_way            — intent → official alternative +
                                        gotchas from current_plan

Module-local helper:
    _is_informative_card(card) — filters "skeleton" cards (every
                                  identifying field empty) so we don't
                                  emit "Consider using ''" recommendations.
                                  All 4 call sites are inside this module.

These three tools could have lived in tools_knowledge.py (they share the
CardIndex / DocsBrain). They're split out because they speak a different
dialect — knowledge tools return raw cards, these synthesize
intent-scoped recommendations and gotcha lists. Keeping them together
makes that semantic layer easier to iterate on.
"""

from __future__ import annotations

from typing import Annotated, Any

from mcp.server.fastmcp import Context
from pydantic import Field

# Intentional cycle — see registry/__init__.py.
from td_mcp import tool_registry as _tr  # noqa: E402
from td_mcp.knowledge.freshness import Provenance
from td_mcp.tool_registry import mcp  # noqa: E402


def _is_informative_card(card: dict) -> bool:
    """Return True only if the card has at least one non-empty identifying field.

    The knowledge corpus occasionally returns skeleton cards (every string field
    is ""). Emitting those as recommendations produces responses like
    ``"Consider using '': "`` which are useless. Filter them out here so
    callers see an honest ``count: 0`` + ``hint`` instead.
    """
    if not isinstance(card, dict):
        return False
    for key in ("op_type", "component_name", "display_name", "snippet_id", "summary"):
        value = card.get(key)
        if isinstance(value, str) and value.strip():
            return True
    return False


@mcp.tool(name="td_recommend_official_component")
async def td_recommend_official_component(
    ctx: Context,
    goal: Annotated[
        str,
        Field(description="What you want to achieve", min_length=1),
    ],
) -> dict[str, Any]:
    """Recommend official palette or built-in operator components for a given goal."""
    finish = _tr._start_tool(ctx, "td_recommend_official_component")
    try:
        idx = _tr._get_card_index(ctx)
        svc = _tr._get_services(ctx)
        provenance = Provenance(source="local_card", td_build=svc.td_build)

        # Search palette components
        palette_results = idx.search(goal, card_types=["palette"], limit=5)
        # Search operators for built-in alternatives
        operator_results = idx.search(goal, card_types=["operators"], limit=5)

        recommendations = []
        for card in palette_results:
            if not _is_informative_card(card):
                continue
            recommendations.append(
                {
                    "type": "palette",
                    "name": card.get("component_name", ""),
                    "display_name": card.get("display_name", ""),
                    "summary": card.get("summary", ""),
                    "when_to_use": card.get("when_to_use", ""),
                }
            )
        for card in operator_results:
            if not _is_informative_card(card):
                continue
            recommendations.append(
                {
                    "type": "operator",
                    "name": card.get("op_type", ""),
                    "display_name": card.get("display_name", ""),
                    "summary": card.get("summary", ""),
                    "family": card.get("family", ""),
                }
            )

        payload: dict[str, Any] = {
            "success": True,
            "goal": goal,
            "recommendations": recommendations,
            "count": len(recommendations),
            "provenance": provenance.to_dict(),
        }
        if not recommendations:
            payload["hint"] = (
                "No informative palette or operator cards matched. Try "
                "td_search_official_docs for operator docs, td_lookup_palette_component "
                "for palette components, or td_memory_recall for saved techniques."
            )

        _tr._audit_log(ctx, "td_recommend_official_component", {"goal": goal})
        return payload
    except Exception as exc:
        _tr._record_tool_error(ctx, "td_recommend_official_component")
        return {"error": str(exc)}
    finally:
        finish()


@mcp.tool(name="td_find_official_example")
async def td_find_official_example(
    ctx: Context,
    query: Annotated[
        str,
        Field(description="Search query for official examples", min_length=1),
    ],
    family: Annotated[
        str | None,
        Field(
            default=None,
            description="Filter by operator family: TOP, CHOP, SOP, etc.",
        ),
    ] = None,
) -> dict[str, Any]:
    """Search for official examples and snippets matching a query."""
    finish = _tr._start_tool(ctx, "td_find_official_example")
    try:
        idx = _tr._get_card_index(ctx)
        svc = _tr._get_services(ctx)
        provenance = Provenance(source="local_card", td_build=svc.td_build)

        # Search snippets
        snippet_results = idx.search(
            query,
            card_types=["snippets"],
            family=family,
            limit=5,
        )
        # Search palette for example components
        palette_results = idx.search(
            query,
            card_types=["palette"],
            family=family,
            limit=5,
        )

        examples = []
        for card in snippet_results:
            examples.append(
                {
                    "type": "snippet",
                    "id": card.get("snippet_id", ""),
                    "display_name": card.get("display_name", ""),
                    "summary": card.get("summary", ""),
                    "family": card.get("family", ""),
                }
            )
        for card in palette_results:
            examples.append(
                {
                    "type": "palette_example",
                    "name": card.get("component_name", ""),
                    "display_name": card.get("display_name", ""),
                    "summary": card.get("summary", ""),
                }
            )

        _tr._audit_log(
            ctx,
            "td_find_official_example",
            {"query": query, "family": family},
        )
        return {
            "success": True,
            "query": query,
            "family": family,
            "examples": examples,
            "count": len(examples),
            "provenance": provenance.to_dict(),
        }
    except Exception as exc:
        _tr._record_tool_error(ctx, "td_find_official_example")
        return {"error": str(exc)}
    finally:
        finish()


@mcp.tool(name="td_explain_better_way")
async def td_explain_better_way(
    ctx: Context,
    intent: Annotated[
        str,
        Field(description="What you intend to do", min_length=1),
    ],
    current_plan: Annotated[
        str | None,
        Field(default=None, description="Current approach to evaluate"),
    ] = None,
) -> dict[str, Any]:
    """Suggest better official alternatives for a given intent, with gotcha warnings."""
    finish = _tr._start_tool(ctx, "td_explain_better_way")
    try:
        idx = _tr._get_card_index(ctx)
        svc = _tr._get_services(ctx)
        provenance = Provenance(source="local_card", td_build=svc.td_build)

        # Search for official alternatives across all card types. Filter out
        # skeleton cards (every identifying field empty) so we don't emit
        # "Consider using '': " recommendations when the corpus has no match.
        raw_alternatives = idx.search(intent, limit=10)
        alternatives = [c for c in raw_alternatives if _is_informative_card(c)]

        # Extract gotchas from operator cards if current_plan mentions specific ops
        gotchas = []
        if current_plan:
            for card in idx.search(current_plan, card_types=["operators"], limit=10):
                if not _is_informative_card(card):
                    continue
                card_gotchas = card.get("common_gotchas", [])
                if card_gotchas:
                    op_name = card.get("op_type", card.get("display_name", ""))
                    for g in card_gotchas:
                        gotchas.append({"operator": op_name, "gotcha": g})

        # Build recommendation
        official_alternative = None
        if alternatives:
            top = alternatives[0]
            name = top.get("op_type") or top.get("component_name") or top.get("snippet_id", "")
            display_name = top.get("display_name", "") or name
            official_alternative = {
                "name": name,
                "display_name": display_name,
                "summary": top.get("summary", ""),
                "family": top.get("family", ""),
            }

        recommendation_parts: list[str] = []
        if official_alternative:
            label = official_alternative["display_name"] or official_alternative["name"]
            summary = official_alternative["summary"]
            if summary:
                recommendation_parts.append(f"Consider using '{label}': {summary}")
            else:
                recommendation_parts.append(f"Consider using '{label}'")
        if gotchas:
            recommendation_parts.append(f"Watch out for {len(gotchas)} known gotcha(s).")
        recommendation = " ".join(recommendation_parts)

        payload: dict[str, Any] = {
            "success": True,
            "intent": intent,
            "current_plan": current_plan,
            "recommendation": recommendation,
            "official_alternative": official_alternative,
            "gotchas": gotchas,
            "provenance": provenance.to_dict(),
        }
        if not recommendation and not gotchas:
            payload["hint"] = (
                "No informative cards matched this intent. Try "
                "td_recommend_official_component with a broader goal, or "
                "td_memory_recall to look for saved techniques."
            )

        _tr._audit_log(ctx, "td_explain_better_way", {"intent": intent})
        return payload
    except Exception as exc:
        _tr._record_tool_error(ctx, "td_explain_better_way")
        return {"error": str(exc)}
    finally:
        finish()
