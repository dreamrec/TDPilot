"""Draft missing parameter semantics from official operator cards."""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from td_mcp.models.brain import DataDomain, ParamCookRisk, ParamSemantics, ParamValueKind

OFFICIAL_DERIVATIVE_DOCS_PREFIX = "https://docs.derivative.ca/"
_FAMILY_SUFFIXES: tuple[DataDomain, ...] = ("TOP", "CHOP", "SOP", "POP", "DAT", "MAT", "COMP")


class ParamSemanticsDraft(BaseModel):
    """Unverified parameter contract inferred from official docs metadata."""

    model_config = ConfigDict(extra="forbid")

    op_type: str = Field(min_length=1)
    name: str = Field(min_length=1)
    label: str = Field(min_length=1)
    value_kind: ParamValueKind
    expected_family: DataDomain | None = None
    tuple_size: int | None = Field(default=None, ge=1)
    enum_values: list[str] = Field(default_factory=list)
    default_strategy: str = Field(min_length=1)
    cook_risk: ParamCookRisk = "unknown"
    validation_rule: str = Field(min_length=1)
    official_source: str
    confidence: Literal["low", "medium", "high"] = "medium"
    needs_live_readback: bool = True
    evidence: list[str] = Field(default_factory=list)

    @field_validator("official_source")
    @classmethod
    def _source_must_be_official_derivative_docs(cls, value: str) -> str:
        if not value.startswith(OFFICIAL_DERIVATIVE_DOCS_PREFIX):
            raise ValueError("draft source must be an official Derivative docs URL")
        return value


class ParamSemanticsDraftReport(BaseModel):
    """Summary of docs-derived parameter semantics draft coverage."""

    model_config = ConfigDict(extra="forbid")

    operator_count: int = 0
    draft_count: int = 0
    drafts: list[ParamSemanticsDraft] = Field(default_factory=list)
    missing_docs: list[str] = Field(default_factory=list)
    skipped_existing: list[str] = Field(default_factory=list)


class ParamSemanticsLiveConfirmationReport(BaseModel):
    """Live readback confirmation for docs-derived parameter semantics drafts."""

    model_config = ConfigDict(extra="forbid")

    ok: bool = False
    operator_count: int = 0
    draft_count: int = 0
    confirmed_count: int = 0
    blocked_count: int = 0
    confirmed_semantics: list[ParamSemantics] = Field(default_factory=list)
    blocked: list[dict[str, Any]] = Field(default_factory=list)
    scratch_path: str = ""
    created_paths: list[str] = Field(default_factory=list)
    cleanup_ok: bool = False
    cleanup_error: str = ""


def draft_param_semantics_from_docs(
    card_index,
    op_types: Iterable[str],
    *,
    existing_registry: Iterable[ParamSemantics] | None = None,
    max_per_operator: int = 32,
) -> ParamSemanticsDraftReport:
    """Draft missing parameter semantics from official CardIndex/DocsBrain cards.

    Drafts are intentionally not returned as trusted ``ParamSemantics`` records.
    They need live parameter readback before promotion into the execution
    registry, which keeps docs-derived guesses out of mutation preflight.
    """
    operators = _dedupe([str(op_type) for op_type in op_types if str(op_type).strip()])
    existing = _existing_keys(existing_registry or [])
    drafts: list[ParamSemanticsDraft] = []
    skipped_existing: list[str] = []
    missing_docs: list[str] = []

    for op_type in operators:
        card = _safe_get_operator(card_index, op_type)
        docs_url = _official_docs_url(card)
        if not card or not docs_url:
            missing_docs.append(op_type)
            continue
        for raw_param in _key_params(card)[:max_per_operator]:
            name = _param_name(raw_param)
            if not name:
                continue
            key = (op_type, name)
            if key in existing:
                skipped_existing.append(f"{op_type}.{name}")
                continue
            drafts.append(_draft_from_param(op_type, raw_param, docs_url))

    return ParamSemanticsDraftReport(
        operator_count=len(operators),
        draft_count=len(drafts),
        drafts=drafts,
        missing_docs=missing_docs,
        skipped_existing=skipped_existing,
    )


async def confirm_param_semantics_drafts_with_live_readback(
    td_client,
    drafts: Iterable[ParamSemanticsDraft],
    *,
    parent_path: str = "/project1",
    scratch_name: str = "tdpilot_param_semantics_probe",
) -> ParamSemanticsLiveConfirmationReport:
    """Confirm docs-derived parameter drafts against live TD parameter readback.

    The function samples operators inside a scratch COMP, reads ``node/params``,
    and only emits trusted ``ParamSemantics`` records when the live parameter
    kind/shape agrees with the draft. Blocked drafts remain blocked evidence,
    not trusted execution contracts.
    """
    draft_list = list(drafts)
    by_op: dict[str, list[ParamSemanticsDraft]] = {}
    for draft in draft_list:
        by_op.setdefault(draft.op_type, []).append(draft)

    scratch_path = f"{parent_path.rstrip('/')}/{scratch_name}"
    confirmed: list[ParamSemantics] = []
    blocked: list[dict[str, Any]] = []
    created_paths: list[str] = []
    cleanup_ok = False
    cleanup_error = ""

    try:
        await td_client.request(
            "node/create",
            {
                "parent_path": parent_path,
                "node_type": "baseCOMP",
                "name": scratch_name,
            },
        )
        for index, (op_type, op_drafts) in enumerate(by_op.items()):
            node_name = _probe_node_name(op_type, index)
            try:
                create_response = await td_client.request(
                    "node/create",
                    {
                        "parent_path": scratch_path,
                        "node_type": op_type,
                        "name": node_name,
                    },
                )
                created_path = _created_path(create_response)
            except Exception as exc:  # noqa: BLE001 - live rejection belongs in evidence.
                created_path = ""
                for draft in op_drafts:
                    blocked.append(_blocked(draft, "create_failed", error=str(exc)))
            if not created_path:
                for draft in op_drafts:
                    if not any(item.get("param") == f"{draft.op_type}.{draft.name}" for item in blocked):
                        blocked.append(_blocked(draft, "create_returned_no_path"))
                continue

            created_paths.append(created_path)
            try:
                params_response = await td_client.request("node/params", {"path": created_path})
            except Exception as exc:  # noqa: BLE001 - live readback failure belongs in evidence.
                for draft in op_drafts:
                    blocked.append(_blocked(draft, "readback_failed", error=str(exc)))
                continue

            live_params = _live_params_by_name(params_response)
            for draft in op_drafts:
                live = live_params.get(draft.name)
                if live is None:
                    blocked.append(_blocked(draft, "missing_live_parameter"))
                    continue
                mismatch = _live_mismatch(draft, live)
                if mismatch is not None:
                    blocked.append(mismatch)
                    continue
                confirmed.append(_confirmed_semantic_from_draft(draft, live))
    finally:
        try:
            await td_client.request("node/delete", {"path": scratch_path})
            cleanup_ok = True
        except Exception as exc:  # noqa: BLE001 - cleanup status is part of report.
            cleanup_error = str(exc)
        close = getattr(td_client, "close", None)
        if close is not None:
            await close()

    return ParamSemanticsLiveConfirmationReport(
        ok=not blocked and cleanup_ok,
        operator_count=len(by_op),
        draft_count=len(draft_list),
        confirmed_count=len(confirmed),
        blocked_count=len(blocked),
        confirmed_semantics=confirmed,
        blocked=blocked,
        scratch_path=scratch_path,
        created_paths=created_paths,
        cleanup_ok=cleanup_ok,
        cleanup_error=cleanup_error,
    )


def _draft_from_param(op_type: str, raw_param: dict[str, Any] | str, docs_url: str) -> ParamSemanticsDraft:
    name = _param_name(raw_param)
    label = _param_label(raw_param, name)
    raw_type = _param_type(raw_param)
    note = _param_note(raw_param)
    value_kind, expected_family, tuple_size, confidence = _infer_value_contract(
        name=name,
        label=label,
        raw_type=raw_type,
        note=note,
    )
    return ParamSemanticsDraft(
        op_type=op_type,
        name=name,
        label=label,
        value_kind=value_kind,
        expected_family=expected_family,
        tuple_size=tuple_size,
        default_strategy=f"confirm_{name}_from_docs_then_live_readback",
        cook_risk=_cook_risk_for(value_kind, raw_type=raw_type, note=note),
        validation_rule=_validation_rule_for(value_kind),
        official_source=docs_url,
        confidence=confidence,
        needs_live_readback=True,
        evidence=[f"docs:{op_type}", f"param:{op_type}.{name}", f"raw_type:{raw_type or 'unknown'}"],
    )


def _confirmed_semantic_from_draft(
    draft: ParamSemanticsDraft,
    live: dict[str, Any],
) -> ParamSemantics:
    enum_values = _live_enum_values(live) or list(draft.enum_values)
    return ParamSemantics(
        op_type=draft.op_type,
        name=draft.name,
        label=str(live.get("label") or draft.label),
        value_kind=draft.value_kind,
        expected_family=draft.expected_family,
        tuple_size=draft.tuple_size,
        enum_values=enum_values,
        default_strategy=f"live_confirmed_{draft.default_strategy}",
        cook_risk=draft.cook_risk,
        validation_rule=draft.validation_rule,
        official_source=draft.official_source,
    )


def _live_mismatch(draft: ParamSemanticsDraft, live: dict[str, Any]) -> dict[str, Any] | None:
    live_type = _live_type(live)
    live_value = live.get("value")
    if draft.value_kind == "tuple":
        actual_size = _live_tuple_size(live)
        if draft.tuple_size is not None and actual_size != draft.tuple_size:
            return _blocked(
                draft,
                "tuple_shape_mismatch",
                live_type=live_type,
                live_value=live_value,
            )
        return None
    if draft.value_kind == "enum":
        if not _live_enum_values(live) and not draft.enum_values:
            return _blocked(draft, "missing_live_menu_values", live_type=live_type, live_value=live_value)
        if "menu" not in live_type.lower() and not _live_enum_values(live):
            return _blocked(draft, "value_kind_mismatch", live_type=live_type, live_value=live_value)
        return None
    if draft.value_kind == "bool" and not _live_looks_bool(live):
        return _blocked(draft, "value_kind_mismatch", live_type=live_type, live_value=live_value)
    if draft.value_kind == "op_ref" and not _live_looks_op_ref(draft, live):
        return _blocked(draft, "value_kind_mismatch", live_type=live_type, live_value=live_value)
    if draft.value_kind == "int" and not _live_looks_int(live):
        return _blocked(draft, "value_kind_mismatch", live_type=live_type, live_value=live_value)
    if draft.value_kind == "float" and not _live_looks_float(live):
        return _blocked(draft, "value_kind_mismatch", live_type=live_type, live_value=live_value)
    if draft.value_kind in {"path", "string"} and not _live_looks_string(live):
        return _blocked(draft, "value_kind_mismatch", live_type=live_type, live_value=live_value)
    return None


def _blocked(draft: ParamSemanticsDraft, reason: str, **extra: Any) -> dict[str, Any]:
    payload = {
        "op_type": draft.op_type,
        "param": f"{draft.op_type}.{draft.name}",
        "reason": reason,
    }
    payload.update(extra)
    return payload


def _live_params_by_name(response: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(response, dict):
        return {}
    raw = response.get("parameters") or response.get("params") or {}
    records: list[dict[str, Any]]
    if isinstance(raw, dict):
        records = [
            {"name": name, **value} if isinstance(value, dict) else {"name": name, "value": value}
            for name, value in raw.items()
        ]
    elif isinstance(raw, list):
        records = [item for item in raw if isinstance(item, dict)]
    else:
        records = []
    return {
        str(record.get("name") or record.get("parameter") or "").strip(): record
        for record in records
        if str(record.get("name") or record.get("parameter") or "").strip()
    }


def _created_path(response: Any) -> str:
    if not isinstance(response, dict):
        return ""
    node = response.get("node")
    if isinstance(node, dict) and node.get("path"):
        return str(node["path"])
    return str(response.get("path") or "")


def _probe_node_name(op_type: str, index: int) -> str:
    stem = re.sub(r"[^A-Za-z0-9_]+", "_", op_type).strip("_") or "op"
    return f"probe_{index:02d}_{stem[:32]}"


def _live_type(live: dict[str, Any]) -> str:
    return str(live.get("type") or live.get("value_kind") or live.get("style") or "")


def _live_tuple_size(live: dict[str, Any]) -> int | None:
    value = live.get("value")
    if isinstance(value, list | tuple):
        return len(value)
    match = re.search(r"(?:float|int|vec)([234])\b", _live_type(live).lower())
    return int(match.group(1)) if match else None


def _live_enum_values(live: dict[str, Any]) -> list[str]:
    for key in ("menu_names", "menuNames", "menu_items", "menuItems", "enum_values", "values"):
        value = live.get(key)
        if isinstance(value, list):
            return [str(item) for item in value if str(item)]
    return []


def _live_looks_bool(live: dict[str, Any]) -> bool:
    live_type = _live_type(live).lower()
    value = live.get("value")
    return "toggle" in live_type or "bool" in live_type or isinstance(value, bool) or value in {0, 1}


def _live_looks_op_ref(draft: ParamSemanticsDraft, live: dict[str, Any]) -> bool:
    text = f"{_live_type(live)} {live.get('label') or ''}".lower()
    family_match = draft.expected_family is None or draft.expected_family.lower() in text
    value = live.get("value")
    return family_match and ("path" in text or "operator" in text or isinstance(value, str))


def _live_looks_int(live: dict[str, Any]) -> bool:
    live_type = _live_type(live).lower()
    value = live.get("value")
    return "int" in live_type or (isinstance(value, int) and not isinstance(value, bool))


def _live_looks_float(live: dict[str, Any]) -> bool:
    live_type = _live_type(live).lower()
    value = live.get("value")
    return any(token in live_type for token in ("float", "double", "number")) or (
        isinstance(value, int | float) and not isinstance(value, bool)
    )


def _live_looks_string(live: dict[str, Any]) -> bool:
    live_type = _live_type(live).lower()
    value = live.get("value")
    return any(token in live_type for token in ("str", "text", "path")) or isinstance(value, str)


def _infer_value_contract(
    *,
    name: str,
    label: str,
    raw_type: str,
    note: str,
) -> tuple[ParamValueKind, DataDomain | None, int | None, Literal["low", "medium", "high"]]:
    text = " ".join([name, label, raw_type, note]).lower()
    expected_family = _expected_family_from_text(text)
    if expected_family and ("path" in text or "operator" in text or "op " in text):
        return "op_ref", expected_family, None, "high"
    if "toggle" in text or "bool" in text or "enable" in text:
        return "bool", None, None, "high"
    if "pulse" in text:
        return "pulse", None, None, "high"
    if "menu" in text:
        return "enum", None, None, "medium"
    tuple_size = _tuple_size_from_type(text)
    if tuple_size:
        return "tuple", None, tuple_size, "high"
    if "integer" in text or re.search(r"\bint\b", text):
        return "int", None, None, "high"
    if "float" in text or "double" in text or "number" in text:
        return "float", None, None, "high"
    if "path" in text:
        return "path", None, None, "medium"
    if "string" in text or "text" in text:
        return "string", None, None, "medium"
    return "string", None, None, "low"


def _expected_family_from_text(text: str) -> DataDomain | None:
    for family in _FAMILY_SUFFIXES:
        if re.search(rf"\b{family.lower()}\b", text):
            return family
    return None


def _tuple_size_from_type(text: str) -> int | None:
    match = re.search(r"(?:float|int|vec)([234])\b", text)
    if match:
        return int(match.group(1))
    if "rgba" in text:
        return 4
    if "rgb" in text:
        return 3
    if "xy" in text or "width and height" in text:
        return 2
    return None


def _cook_risk_for(value_kind: ParamValueKind, *, raw_type: str, note: str) -> ParamCookRisk:
    text = f"{raw_type} {note}".lower()
    if value_kind == "op_ref":
        return "high"
    if any(token in text for token in ("resolution", "depth", "buffer", "format", "cook", "feedback")):
        return "high"
    if value_kind in {"tuple", "enum", "path", "pulse"}:
        return "medium"
    if value_kind in {"float", "int"}:
        return "medium"
    if value_kind == "bool":
        return "low"
    return "unknown"


def _validation_rule_for(value_kind: ParamValueKind) -> str:
    return {
        "op_ref": "live_readback_operator_reference",
        "path": "live_readback_path",
        "tuple": "live_readback_tuple_shape",
        "enum": "live_readback_menu_values",
        "pulse": "live_readback_pulse_parameter",
        "bool": "live_readback_bool_toggle",
        "float": "live_readback_numeric_float",
        "int": "live_readback_numeric_int",
        "string": "live_readback_string",
    }.get(value_kind, "live_readback_parameter")


def _existing_keys(existing_registry: Iterable[ParamSemantics]) -> set[tuple[str, str]]:
    keys: set[tuple[str, str]] = set()
    for item in existing_registry:
        op_type = getattr(item, "op_type", None)
        name = getattr(item, "name", None)
        if op_type and name:
            keys.add((str(op_type), str(name)))
    return keys


def _safe_get_operator(card_index, op_type: str) -> dict | None:
    if card_index is None:
        return None
    try:
        card = card_index.get_operator(op_type)
    except Exception:
        return None
    return card if isinstance(card, dict) else None


def _official_docs_url(card: dict | None) -> str:
    if not isinstance(card, dict):
        return ""
    value = card.get("docs_url") or card.get("source_url")
    return value if isinstance(value, str) and value.startswith(OFFICIAL_DERIVATIVE_DOCS_PREFIX) else ""


def _key_params(card: dict) -> list[dict[str, Any] | str]:
    raw = card.get("key_params") or card.get("parameters") or []
    return raw if isinstance(raw, list) else []


def _param_name(raw_param: dict[str, Any] | str) -> str:
    if isinstance(raw_param, dict):
        value = raw_param.get("name")
        return str(value).strip() if value else ""
    return raw_param.strip().splitlines()[-1] if raw_param.strip() else ""


def _param_label(raw_param: dict[str, Any] | str, fallback: str) -> str:
    if isinstance(raw_param, dict):
        value = raw_param.get("label")
        if value:
            return str(value).strip()
    return fallback


def _param_type(raw_param: dict[str, Any] | str) -> str:
    if isinstance(raw_param, dict):
        value = raw_param.get("type") or raw_param.get("value_kind")
        return str(value).strip() if value else ""
    return ""


def _param_note(raw_param: dict[str, Any] | str) -> str:
    if isinstance(raw_param, dict):
        value = raw_param.get("note") or raw_param.get("summary")
        return str(value).strip() if value else ""
    return ""


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


__all__ = [
    "ParamSemanticsLiveConfirmationReport",
    "ParamSemanticsDraft",
    "ParamSemanticsDraftReport",
    "confirm_param_semantics_drafts_with_live_readback",
    "draft_param_semantics_from_docs",
]
