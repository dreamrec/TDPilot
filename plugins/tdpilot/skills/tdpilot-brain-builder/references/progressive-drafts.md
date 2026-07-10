# Progressive Draft Skeletons

These examples show how a proposal grows from grounded requirements into a
small operator graph. They are not universal recipes. Always use the
`authoring_contract`, candidate cards, availability, and parameter semantics
returned by the current `td_brain_ground` call.

## 2D: Audio-controlled TOP

Grounding must cover an audio source, analysis, normalization, a visible TOP
source, a bounded numeric binding, a stable TOP output, signal activity, target
readback, and temporal visual change.

```json
{
  "label": "Audio-controlled 2D texture",
  "profiles": ["audio_reactive"],
  "concepts": [
    {
      "id": "audio_source",
      "label": "Audio source",
      "role": "source",
      "domain": "CHOP",
      "op_type": "audiofileinCHOP"
    },
    {
      "id": "audio_level",
      "label": "RMS analysis",
      "role": "process",
      "domain": "CHOP",
      "op_type": "analyzeCHOP",
      "params": {"function": "rmspower"}
    },
    {
      "id": "control_out",
      "label": "Bounded control",
      "role": "output",
      "domain": "CHOP",
      "op_type": "nullCHOP"
    },
    {
      "id": "texture",
      "label": "Animated texture",
      "role": "source",
      "domain": "TOP",
      "op_type": "noiseTOP"
    },
    {
      "id": "visual_level",
      "label": "Audio-driven level",
      "role": "process",
      "domain": "TOP",
      "op_type": "levelTOP"
    },
    {
      "id": "output",
      "label": "Stable output",
      "role": "output",
      "domain": "TOP",
      "op_type": "nullTOP"
    }
  ],
  "edges": [
    {"source": "audio_source", "target": "audio_level", "kind": "data"},
    {"source": "audio_level", "target": "control_out", "kind": "data"},
    {"source": "texture", "target": "visual_level", "kind": "data"},
    {
      "source": "control_out",
      "target": "visual_level",
      "kind": "control",
      "binding": {
        "mode": "chop_reference_expression",
        "source_channel": 0,
        "target_param": "brightness1"
      }
    },
    {"source": "visual_level", "target": "output", "kind": "data"}
  ],
  "required_ops": [
    "audiofileinCHOP",
    "analyzeCHOP",
    "nullCHOP",
    "noiseTOP",
    "levelTOP",
    "nullTOP"
  ],
  "validation_needs": [
    "audio_signal_activity",
    "control_binding_readback",
    "nonblack_output",
    "temporal_change"
  ],
  "explanation": "A bounded CHOP channel controls a registry-backed numeric parameter on the TOP chain."
}
```

Before proposing:

- Replace `audiofileinCHOP` only when grounding proves the user's file or device
  source and the current TD build supports it.
- Add a normalization operator if the grounding contract requires one.
- Confirm `brightness1` and the analysis enum are present in returned parameter
  semantics. Do not substitute a remembered alias.
- A static value for `visual_level.brightness1` conflicts with the control
  binding and must be removed or deliberately represented as part of a
  supported transform.

## 3D: Rendered object with a stable TOP

Grounding must cover geometry, material, camera, optional lighting, render,
spatial framing, and the stable output. This skeleton deliberately leaves
project-specific transforms and OP-reference parameter spellings to grounding.

```json
{
  "label": "Grounded 3D render",
  "profiles": ["render_pipeline"],
  "concepts": [
    {
      "id": "geometry",
      "label": "Renderable geometry",
      "role": "source",
      "domain": "COMP",
      "op_type": "geometryCOMP",
      "params": {"material": "${path:material}"}
    },
    {
      "id": "material",
      "label": "Surface material",
      "role": "process",
      "domain": "MAT",
      "op_type": "phongMAT"
    },
    {
      "id": "camera",
      "label": "Framing camera",
      "role": "control",
      "domain": "COMP",
      "op_type": "cameraCOMP"
    },
    {
      "id": "light",
      "label": "Key light",
      "role": "control",
      "domain": "COMP",
      "op_type": "lightCOMP"
    },
    {
      "id": "render",
      "label": "3D render",
      "role": "process",
      "domain": "TOP",
      "op_type": "renderTOP",
      "params": {
        "geometry": "${path:geometry}",
        "cameras": "${path:camera}",
        "lights": "${path:light}"
      }
    },
    {
      "id": "output",
      "label": "Stable render output",
      "role": "output",
      "domain": "TOP",
      "op_type": "nullTOP"
    }
  ],
  "edges": [
    {"source": "material", "target": "geometry", "kind": "reference"},
    {"source": "geometry", "target": "render", "kind": "reference"},
    {"source": "camera", "target": "render", "kind": "reference"},
    {"source": "light", "target": "render", "kind": "reference"},
    {"source": "render", "target": "output", "kind": "data"}
  ],
  "required_ops": [
    "geometryCOMP",
    "phongMAT",
    "cameraCOMP",
    "lightCOMP",
    "renderTOP",
    "nullTOP"
  ],
  "validation_needs": [
    "geometry_present",
    "material_assigned",
    "camera_present",
    "render_references_resolve",
    "nonblack_output"
  ],
  "explanation": "A grounded render pipeline with explicit OP references and a stable TOP output."
}
```

Before proposing:

- Inspect a new `geometryCOMP`; TD 2025 may create a POP child rather than the
  SOP geometry the concept expects.
- Use only OP-reference parameter names and cardinality returned by parameter
  semantics. For example, a build may expose plural render reference styles.
- Add camera transform, geometry transform, lighting, fog, depth, or material
  modulation only when those requested facets are represented and validated.
- If audio reactivity is requested, add a separate CHOP module and an explicit
  supported control binding. Mentioning modulation in `explanation` does not
  create it.

## Proposal Gate

Pass the original `grounding_id` and `draft_schema_version="2"`. After review,
inspect server-recomputed `intent_coverage`, `uncovered_requirement_ids`,
`unresolved_semantic_edges`, and stripped parameters. Execute only when required
coverage is complete and every semantic edge has a concrete lowering.
