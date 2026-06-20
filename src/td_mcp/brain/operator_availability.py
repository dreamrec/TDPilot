"""Live operator availability sampling for atlas gap review."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any


def build_availability_targets(atlas_report: dict[str, Any]) -> list[dict[str, Any]]:
    """Build deprecated-gap and replacement-op sampling targets from atlas audit output."""
    coverage = atlas_report.get("docsbrain_operator_coverage", {})
    deprecated_gaps = coverage.get("deprecated_missing_operator_cards", [])
    if not isinstance(deprecated_gaps, list):
        return []

    targets: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str | None]] = set()

    for gap in sorted(deprecated_gaps, key=lambda item: str(item.get("op_type") or "")):
        if not isinstance(gap, dict):
            continue
        op_type = str(gap.get("op_type") or "").strip()
        if not op_type:
            continue

        gap_target = {
            "op_type": op_type,
            "family": gap.get("family"),
            "role": "deprecated_gap",
            "gap_status": gap.get("gap_status"),
            "replacement_for": None,
        }
        _append_unique_target(targets, seen, gap_target)

        replacements = gap.get("replacement_op_types") or []
        if not isinstance(replacements, list):
            continue
        for replacement in sorted({str(item).strip() for item in replacements if str(item).strip()}):
            _append_unique_target(
                targets,
                seen,
                {
                    "op_type": replacement,
                    "family": None,
                    "role": "replacement",
                    "gap_status": None,
                    "replacement_for": op_type,
                },
            )

    return targets


async def sample_operator_availability(
    td_client: Any,
    targets: list[dict[str, Any]],
    *,
    parent_path: str = "/project1",
    scratch_name: str = "tdpilot_availability_probe",
) -> dict[str, Any]:
    """Create each target in a scratch COMP and report whether TD accepts it."""
    scratch_path = f"{parent_path.rstrip('/')}/{scratch_name}"
    results: list[dict[str, Any]] = []
    cleanup_ok = False
    cleanup_error = ""

    try:
        health = await td_client.health_check()
        await td_client.request(
            "node/create",
            {
                "parent_path": parent_path,
                "node_type": "baseCOMP",
                "name": scratch_name,
            },
        )

        for index, target in enumerate(targets):
            op_type = str(target.get("op_type") or "").strip()
            result = {
                "op_type": op_type,
                "family": target.get("family"),
                "role": target.get("role"),
                "gap_status": target.get("gap_status"),
                "replacement_for": target.get("replacement_for"),
                "available": False,
                "created_path": "",
                "error": "",
            }
            if not op_type:
                result["error"] = "missing op_type"
                results.append(result)
                continue

            try:
                create_response = await td_client.request(
                    "node/create",
                    {
                        "parent_path": scratch_path,
                        "node_type": op_type,
                        "name": _sample_node_name(op_type, index),
                    },
                )
                created_path = _created_path(create_response)
                result["available"] = bool(created_path)
                result["created_path"] = created_path
                if not created_path:
                    result["error"] = "node/create returned no path"
            except Exception as exc:  # noqa: BLE001 - report live TD rejection text.
                result["error"] = str(exc)
            results.append(result)

    finally:
        try:
            await td_client.request("node/delete", {"path": scratch_path})
            cleanup_ok = True
        except Exception as exc:  # noqa: BLE001 - cleanup status belongs in report.
            cleanup_error = str(exc)
        close = getattr(td_client, "close", None)
        if close is not None:
            await close()

    available_count = sum(1 for item in results if item["available"])
    report_ok = cleanup_ok and len(results) == len(targets)

    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "ok": report_ok,
        "parent_path": parent_path,
        "scratch_name": scratch_name,
        "scratch_path": scratch_path,
        "td_health": health if "health" in locals() else None,
        "target_count": len(targets),
        "available_count": available_count,
        "unavailable_count": len(results) - available_count,
        "cleanup_ok": cleanup_ok,
        "cleanup_error": cleanup_error,
        "results": results,
    }


def _append_unique_target(
    targets: list[dict[str, Any]],
    seen: set[tuple[str, str, str | None]],
    target: dict[str, Any],
) -> None:
    key = (
        str(target.get("op_type") or ""),
        str(target.get("role") or ""),
        target.get("replacement_for"),
    )
    if key in seen:
        return
    seen.add(key)
    targets.append(target)


def _sample_node_name(op_type: str, index: int) -> str:
    stem = re.sub(r"[^A-Za-z0-9_]+", "_", op_type).strip("_").lower() or "op"
    return f"probe_{index:02d}_{stem[:32]}"


def _created_path(response: Any) -> str:
    if not isinstance(response, dict):
        return ""
    node = response.get("node")
    if isinstance(node, dict) and node.get("path"):
        return str(node["path"])
    if response.get("path"):
        return str(response["path"])
    return ""
