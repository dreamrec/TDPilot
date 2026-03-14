---
name: popx-touchdesigner
description: >
  Local POPX knowledge base and workflow for TouchDesigner. Use when the user
  mentions POPX, popsextension, POPX examples, POPX operators, or wants to
  build, inspect, explain, debug, or modify POPX-based setups in TouchDesigner
  using the bundled POPX reference corpus and live example loader when available.
---

# POPX TouchDesigner

POPx is a paid plugin — its documentation is copyrighted and not distributed with TDPilot.
You must build the reference files locally from your own licensed copy (see `references/BUILD.md`).

This skill is backed by:

- A locally-generated reference catalog in `references/` (user must build — see `references/BUILD.md`)
- A live example loader in the open TouchDesigner project at `/EXAMPLE_LOADER`
- Build scripts in `scripts/` for generating references from your own POPx installation

If you are modifying the live TouchDesigner project with `td_` tools, also follow the `tdpilot-core` skill.

## Quick Start

1. Build references first if not done: see `references/BUILD.md`.
2. Open `references/overview.md`.
3. Run `python3 scripts/search_popx_refs.py "<query>"` if the request is broad or ambiguous.
4. Open the smallest relevant reference file:
   - `references/guides.md`
   - `references/operators-generators.md`
   - `references/operators-falloffs.md`
   - `references/operators-modifiers.md`
   - `references/operators-tools.md`
   - `references/operators-simulations.md`
   - `references/examples.md`
4. If exact wiring or working values matter, inspect the live example loader, not just the generated markdown.

## Operator Workflow

Use the docs references for operator semantics and parameter intent.

- For generators, falloffs, modifiers, tools, or simulations, open the matching operator family file first.
- Use `references/catalog.json` only through `scripts/search_popx_refs.py`; do not load the JSON into context unless necessary.
- Prefer operator pages over examples when the user asks how an operator works.
- Prefer examples over operator pages when the user asks for a known-good setup, working values, or a finished pattern to recreate.

## Example Workflow

When the user refers to a shipped example or wants a POPX setup that already exists:

1. Open `references/examples.md` and find the example entry.
2. Use the related docs listed there to understand the operator set involved.
3. If you need exact values, inspect the live example inside TouchDesigner:
   - Read `/EXAMPLE_LOADER` parameters to confirm the example menu and current selection.
   - Set `/EXAMPLE_LOADER` parameter `Example` to the desired entry.
   - Pulse `/EXAMPLE_LOADER/example` parameter `enableexternaltoxpulse` or pulse loader `Reload`.
   - Read `/EXAMPLE_LOADER/example/description`.
   - Inspect `/EXAMPLE_LOADER/example` with `td_get_nodes`, `td_get_params`, `td_get_connections`, and `td_get_errors`.
4. Treat the loaded example as the source of truth for working values.

Use the live loader when the user asks for:

- The exact nodes used in an example
- The values that make an example work
- How an example is wired
- Which operator chain is closest to a new requested effect

## Building New POPX Networks

When creating a new POPX setup:

1. Search the references for the requested effect and nearby operators.
2. Check `references/examples.md` for the closest shipped example.
3. Reuse the example’s operator order and key parameter patterns when possible.
4. Adapt only the parts that differ from the user’s request.
5. After modifying the live project, run `td_get_errors` on the affected area.

Default mental model:

- Generator creates or converts geometry
- Falloff defines influence
- Modifier transforms or colors based on attributes and falloffs
- Tool prepares, converts, renders, or extracts
- Simulation solves time-based behavior

## Search and Navigation

Use these commands from the skill directory:

```bash
python3 scripts/search_popx_refs.py "soft body"
python3 scripts/search_popx_refs.py "infection falloff interactive" --limit 6
python3 scripts/search_popx_refs.py "path tracer glass" --examples
python3 scripts/search_popx_refs.py "attribute to index" --docs
```

To build or rebuild references from your licensed POPx copy (requires `pip install beautifulsoup4`):

```bash
python3 scripts/build_popx_refs.py --docs-root "/path/to/popsextension.com/docs" --examples-root "/path/to/POPX_1_2_1"
```

See `references/BUILD.md` for full instructions.

Search first when:

- The user names an effect but not an operator
- Multiple POPX families could match
- You need the closest existing example quickly

## References

Load only the file you need:

- `references/overview.md`: corpus summary and source locations
- `references/guides.md`: installation, getting started, tutorials, release notes
- `references/operators-generators.md`: Convert, Explode, Instancer, Subdivider, Sweep
- `references/operators-falloffs.md`: Attribute, Combine, Curve, Infection, Noise, Object, Remap, Shape, Spread, Texture
- `references/operators-modifiers.md`: Advect, Aim, Color Modifier, Magnetize, Move Along Curve, Move Along Mesh, Noise Modifier, Pivot, Randomize, Relax, Spring Modifier, Transform Modifier
- `references/operators-tools.md`: Apply Attributes, Attribute To Index, Constraint Property, Constraints, Delete, Extract Attributes, Geometry, Light, Material, Measure, Merge, Orient Curve, Orient Mesh, Path Tracer, POPX To, Preview Falloff, Reorient, SBPP, SSFR, Unpack, Visualize Frame, Voxelize
- `references/operators-simulations.md`: DLA, DLG, Flow, Mesh Fill, Particle, Physarum, SA, Soft Body
- `references/examples.md`: all 54 shipped examples with descriptions, top nodes, and extracted working values

## Guardrails

- Do not invent POPX operators or parameter names when the local docs disagree.
- Do not assume an example’s values from memory; load the example if precision matters.
- Do not trust one example alone when the docs and the live example disagree; inspect both and state the difference.
- When a request is novel, start from the nearest example and explain what you are borrowing.
