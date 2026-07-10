# Working with TDPilot — the everyday guide

This guide is for the working TD artist (not the Python power user) — someone who:

- knows basic TouchDesigner navigation
- can build small TOP / CHOP / COMP chains
- is not a Python-heavy power user
- wants AI help without giving up control

If that is you, good news:

TDPilot can help a lot.

But you have to use it the right way.

## The Mental Model

Do not think:

"The AI will build my project."

Think:

"The AI is my fast assistant inside TouchDesigner. I still steer. It helps me inspect, scaffold, debug, document, and reuse."

That shift is everything.

## What TDPilot Does Best For You

For a mid-level user, the highest-value wins are:

- understanding an unfamiliar patch quickly
- creating standard node chains faster
- fixing errors with structured inspection
- exposing parameters and organizing COMPs
- saving useful subnet patterns into memory
- recalling those patterns later instead of rebuilding from scratch

## What You Need Before You Start

You need:

- TouchDesigner running
- the TDPilot MCP server running
- the TDPilot TD component installed
- an MCP client such as Claude Desktop or Cursor

Recommended local setup from this repo:

```bash
uv sync --extra dev
uv run tdpilot
```

Recommended packaged runtime:

```bash
npx -y tdpilot
```

Before a session, run:

```bash
uv run tdpilot doctor --json
```

## The Only Workflow You Really Need

Use this every time:

1. Inspect first.
2. Ask for a narrow goal.
3. Make one chunk of changes.
4. Verify errors and cooking.
5. Save what worked.

That is the real TDPilot workflow.

## Your First 8 Useful Commands

If you only remember a few tools, remember these:

- `td_get_info`
- `td_get_nodes`
- `td_get_node_detail`
- `td_get_params`
- `td_set_params`
- `td_create_node`
- `td_connect_nodes`
- `td_get_errors`

If you add four more, add:

- `td_snapshot_scene`
- `td_restore_snapshot`
- `td_memory_learn`
- `td_memory_save`

## How To Prompt The AI Well

Bad prompt:

"Make something cool."

Better prompt:

"Inspect `/project1` first. Then build a minimal audio-reactive TOP chain under `/project1/sketch1`. Work in small steps. After each step, check for errors. Keep it simple and editable."

Good prompt:

"Inspect `/project1/sketch1` first and summarize the current nodes. I want a clean, low-CPU feedback texture chain with 1 control COMP. Build it under `/project1/sketch1`, name nodes clearly, expose only the important parameters, and run `td_get_errors` before you stop."

The AI works better when you specify:

- target path
- goal
- constraints
- whether to inspect first
- whether to validate at the end

## Your Daily Session Routine

### 1. Open the session safely

Ask:

"Get the current project info and show me the main node structure under `/project1`."

Why:

- it lets the AI orient itself
- it reduces dumb edits in the wrong place

### 2. Pick one small goal

Examples:

- add a stable feedback block
- make a control COMP for three parameters
- inspect why a TOP is black
- build an audio-reactive displacement chain
- clean up naming and spacing in a COMP

### 3. Make the AI inspect before editing

Say:

"Inspect first. Do not edit until you summarize what is there."

This is one of the most important habits.

### 4. Force small steps

Say:

"Make changes in small batches and tell me what changed after each batch."

This keeps the project readable and recoverable.

### 5. End with validation

Say:

"Before stopping, run `td_get_errors` and summarize any remaining warnings or errors."

## When To Use Official Docs And Tutorials

You should not ask the AI to hallucinate TD best practices when the official ecosystem already has them.

Use these sources on purpose:

- Learn TouchDesigner:
  <https://docs.derivative.ca/Learn_TouchDesigner>
- Official tutorials index:
  <https://docs.derivative.ca/Tutorials>
- OP Snippets:
  <https://docs.derivative.ca/OP_Snippets>
- Palette:
  <https://docs.derivative.ca/Palette>

How to combine them with TDPilot:

1. Find the technique in official docs or a trusted tutorial.
2. Rebuild a small clean version inside a TD sandbox.
3. Ask TDPilot to inspect and explain it.
4. Ask TDPilot to learn and save it.
5. Reuse it later with replay or manual adaptation.

That is how you convert the internet into reusable local memory.

## Practical Beginner-to-Intermediate Use Cases

### Use case 1: understand an old patch

Prompt:

"Inspect `/project1` and identify the main COMPs, important TOP chains, custom parameters, and current errors. Do not edit."

### Use case 2: build a clean first version

Prompt:

"Under `/project1/sketch1`, build a minimal noise -> transform -> level -> out chain. Keep naming clean. Then expose a small control COMP or custom parameter page for speed, scale, and brightness."

### Use case 3: learn from official examples

Prompt:

"Find an official example or snippet related to feedback distortion. Summarize the safest built-in approach, then help me build a small custom version."

### Use case 4: debug

Prompt:

"Inspect `/project1/fx1`. Tell me why the output might be black or frozen. Use node detail, params, and errors before suggesting changes."

### Use case 5: save something reusable

Prompt:

"This subnet under `/project1/sketch1/feedback_core` is working well. Learn it, save it with a good name, tags, and notes, then list it back to me."

## The Best Habits To Build Early

- always inspect before writing
- keep work inside a known target COMP
- use snapshots before risky edits
- validate after each meaningful change
- save only patterns that are genuinely reusable
- keep names boring and clear
- prefer small composable techniques over giant magic networks

## The Mistakes To Avoid

- asking for a whole project in one prompt
- letting the AI mutate the root project blindly
- skipping error checks
- turning on high-token image streaming for no reason
- saving every experiment into memory
- assuming replayed techniques are automatically perfect in new contexts

## Your "Good Enough" TDPilot Starter Stack

If you do not want to learn all 114 tools, focus on this stack:

- brain:
  `td_brain_plan`, `td_brain_ground`, `td_brain_propose`,
  `td_brain_execute`, `td_transaction_apply`
- inspect:
  `td_get_info`, `td_get_nodes`, `td_get_node_detail`, `td_get_params`
- build:
  `td_create_node`, `td_connect_nodes`, `td_set_params`
- validate:
  `td_get_errors`, `td_cooking_info`, `td_screenshot`
- protect:
  `td_snapshot_scene`, `td_restore_snapshot`
- remember:
  `td_memory_learn`, `td_memory_save`, `td_memory_recall`

That is enough to get real value.

## Pattern route versus concept route

Use the pattern route when the requested topology or technique composition is
already exact and validated:

```text
td_brain_plan → coverage gate → td_brain_execute
```

Use the concept-authoring route when the request is artistic, multi-domain,
spatial, camera/depth/fog driven, or leaves architecture implicit:

```text
td_brain_ground → host-authored module graph → td_brain_propose
→ coverage gate → td_brain_execute
```

A blocked pattern plan is not permission to execute a partial result. Continue
through concept authoring or clarify the genuinely unresolved input. New plans
must cover required capabilities, inputs, outputs, behaviors, spatial and
quality constraints, bindings, and validation assertions before execution.

## The Right Goal For Month 1

Do not try to master the full surface.

Your month-1 goal should be:

"Build 10 small reusable techniques and learn how to save, recall, and adapt them."

That gives you:

- speed
- confidence
- consistency
- less repeated labor

That is where TDPilot starts becoming a force multiplier.

## Best External Learning Links

- Learn TouchDesigner: <https://docs.derivative.ca/Learn_TouchDesigner>
- Official tutorials index: <https://docs.derivative.ca/Tutorials>
- OP Snippets: <https://docs.derivative.ca/OP_Snippets>
- Palette: <https://docs.derivative.ca/Palette>
- Project class: <https://docs.derivative.ca/Project_Class>
- COMP class: <https://docs.derivative.ca/COMP_Class>
- Page class: <https://docs.derivative.ca/Page_Class>
- Web Server DAT: <https://docs.derivative.ca/Web_Server_DAT>
- WebSocket DAT: <https://docs.derivative.ca/WebSocket_DAT>
- MCP FAQ: <https://modelcontextprotocol.io/faqs>
