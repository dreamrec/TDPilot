# TDPilot For Someone Who Has Never Used MCP Before

This is the manual I would give a real TouchDesigner user, not a hype video.

I am skipping installation on purpose.
This guide starts after TDPilot is already connected and working.

If you have never used MCP before, the most important thing to understand is this:

MCP does not make the AI magical.
It gives the AI hands.

Without MCP, the AI can only talk.
With MCP, the AI can inspect your TouchDesigner project, create nodes, set parameters, check errors, save patterns, and replay useful structures.

That is the difference.

## What TDPilot Actually Is

TDPilot is best understood as four things working together:

1. A bridge between your AI client and a live TouchDesigner session.
2. A set of concrete TouchDesigner tools the AI can call.
3. A small built-in knowledge layer for docs, examples, snippets, and recommendations.
4. A memory system for saving reusable techniques and preferences.

If you think of it as "ChatGPT but for TD," you will probably be disappointed.

If you think of it as "a TouchDesigner assistant that can inspect, build, verify, and remember," you will use it much better.

## What It Is Good At

TDPilot is especially good at:

- reading an unfamiliar patch and explaining it back to you
- building small or medium graph changes quickly
- debugging with evidence instead of guessing
- cleaning up structure and naming
- saving good subnet patterns into reusable memory
- helping you turn repeated TD work into a faster workflow

The value is not that it knows every possible TD trick.

The value is that it can work on the patch with you.

## What It Is Not

TDPilot is not:

- a one-prompt "build my whole show" machine
- a replacement for visual taste
- a replacement for understanding cook behavior, performance, and operator families
- a guarantee that every advanced feature should be trusted blindly
- a giant self-growing brain that automatically learns everything on the internet

It is strong when you use it in small loops.
It gets weaker when you try to hand it the whole project in one sentence.

## The Right Mental Model

Treat TDPilot like a very fast assistant who:

- can read the current state
- can make precise changes
- can follow instructions well
- can forget context if you are vague
- still needs you to steer the work

The best attitude is not:

"Do it all for me."

The best attitude is:

"Help me move faster, make fewer mistakes, and save what works."

## What MCP Feels Like In Practice

A normal first-time reaction to MCP is:

"So do I just chat with it?"

Yes, but the chat now has tool access behind it.

That means a good session looks like this:

1. You tell the AI where to look.
2. It inspects the current patch.
3. You give it one small goal.
4. It makes a limited change.
5. It checks errors and reports back.
6. You keep going or save the result into memory.

That is the real workflow.

It is much closer to working with a technical assistant than using a search engine.

## Your First Rule: Inspect Before Editing

This is the habit that saves the most pain.

Before asking for changes, tell it to inspect first.

Good:

"Inspect `/project1` first. Summarize the main COMPs, important outputs, custom parameters, and any errors. Do not edit yet."

Bad:

"Make this better."

When the AI inspects first, you get:

- orientation
- fewer random edits
- better prompts for the next step
- a much lower chance of damaging the wrong area

## Your Second Rule: Give It A Work Area

Always tell it where to work.

Examples:

- `/project1/sketch1`
- `/project1/fx/feedback_core`
- `/project1/ui/control_panel`

That matters because the AI works better when the target is clear.

It also helps you keep experiments contained.

## Your Third Rule: Ask For One Chunk At A Time

Do not ask for a whole project in one go.

Better pattern:

1. inspect
2. build a small part
3. verify
4. continue

For example:

"Under `/project1/sketch1`, build only the base TOP chain first: noise, transform, level, out. Keep naming clear. After that, stop and check errors."

Then:

"Now add one control page or one control COMP for speed, brightness, and scale."

This is how you keep the patch understandable.

## The Small Set Of Tools That Matter Most

You do not need to learn all 88 tools to get real value.

If you are new, focus on these:

- `td_get_info`
- `td_get_nodes`
- `td_get_node_detail`
- `td_get_params`
- `td_create_node`
- `td_connect_nodes`
- `td_set_params`
- `td_get_errors`
- `td_cooking_info`
- `td_snapshot_scene`
- `td_restore_snapshot`
- `td_memory_learn`
- `td_memory_save`
- `td_memory_recall`

Everything else is useful later.
These are the ones that make TDPilot feel real.

## A Good First Session

Here is a realistic first session for a normal TD user.

### Step 1: Ask it to read the patch

Prompt:

"Inspect `/project1` and explain the current structure in plain language. Tell me what looks important and what looks broken. Do not edit anything."

### Step 2: Pick one modest goal

Good early goals:

- clean up naming inside one COMP
- build a simple effect chain
- expose a few parameters
- figure out why a TOP is black
- save a good subnet into memory

### Step 3: Make it work in small steps

Prompt:

"Work only inside `/project1/sketch1`. Make changes in small batches. After each batch, summarize what changed and check for errors."

### Step 4: Protect yourself before risky edits

Prompt:

"Take a snapshot of `/project1/sketch1` before changing structure."

### Step 5: End with verification

Prompt:

"Before stopping, run `td_get_errors` and tell me if anything still needs attention."

That is already enough for a useful session.

## The Best Ways To Use TDPilot

### 1. Patch understanding

This is one of the most underrated uses.

If a patch is messy, old, or made by someone else, TDPilot can help you map it faster.

Ask:

"Inspect `/project1/show_patch` and explain the main data flow, the key COMPs, the likely outputs, and any obvious fragile spots."

### 2. Scaffolding

TDPilot is very good at building the boring first version of something.

Ask:

"Under `/project1/lookdev1`, build a minimal feedback texture chain with clean naming and one obvious output. Keep it simple and editable."

### 3. Debugging

TDPilot becomes useful when you make it diagnose instead of guess.

Ask:

"Inspect `/project1/fx1` and tell me why the output might be black or frozen. Use node detail, parameters, cooking info, and errors before suggesting any edits."

### 4. Cleanup

A lot of TD pain is not creative pain. It is organization pain.

Ask:

"Clean up the nodes inside `/project1/control_tools`: better names, better spacing, clearer flow, but do not change behavior."

### 5. Memory building

This is where the long-term value starts to compound.

Ask:

"Inspect `/project1/techniques/audio_gate_core`. If it is reusable, learn it, save it with a proper name, tags, and notes, then list it back to me."

## What Memory Really Means Here

People hear "memory" and imagine an autonomous AI brain.

That is not what this is.

In TDPilot, memory is mainly:

- saved techniques
- saved preferences
- a local knowledge corpus
- your current live project context

The best way to think about it is:

memory is your reusable studio knowledge, not the AI's soul.

## How To Build Useful Memory

The memory system gets better when you feed it clean, proven things.

Good memory candidates:

- a stable feedback core
- a clean control COMP pattern
- a beat-reactive CHOP setup
- a nice reusable level-blur-composite stack
- a diagnostics helper subnet
- a standard out wrapper

Bad memory candidates:

- giant experimental spaghetti
- unfinished sketches
- hacks you do not understand
- anything that only worked once by accident

The rule is simple:

save patterns, not chaos.

## How To Use Official Docs, Tutorials, And AI Together

This is one of the smartest ways to use TDPilot.

Do not ask the AI to invent TouchDesigner best practice from nothing if official material already exists.

Use this loop:

1. Find a relevant official doc page, tutorial, snippet, or palette example.
2. Rebuild the useful part in a sandbox COMP.
3. Ask TDPilot to inspect it and explain what matters.
4. Simplify it.
5. Save the distilled version into memory.

That is how you turn public learning material into a private working library.

Good sources:

- [Learn TouchDesigner](https://docs.derivative.ca/Learn_TouchDesigner)
- [Tutorials](https://docs.derivative.ca/Tutorials)
- [OP Snippets](https://docs.derivative.ca/OP_Snippets)
- [Palette](https://docs.derivative.ca/Palette)

## How To Talk To The AI So It Helps Instead Of Wandering

The best prompts usually contain five things:

1. where to work
2. what the goal is
3. how careful to be
4. whether to inspect first
5. how to validate at the end

Bad prompt:

"Make something nice."

Better prompt:

"Inspect `/project1/sketch1` first. Then build a minimal audio-reactive TOP chain under that COMP. Keep it low-complexity, use clear node names, and run `td_get_errors` before you stop."

Another strong prompt:

"Do not improvise architecture. Work only inside `/project1/lookdev2`. Build one small chunk at a time, explain each chunk, and keep the result easy for a human to edit."

## What Usually Goes Wrong

These are the most common mistakes:

- asking for too much at once
- not telling it where to work
- skipping inspection
- skipping error checks
- saving too many low-quality things into memory
- treating memory as a junk drawer instead of a library
- expecting "AI taste" to replace artistic judgement

If you avoid those, your results get better very quickly.

## A Good Weekly Habit

If you want real value from TDPilot, build one small habit:

At the end of each week, save one or two things that were genuinely useful.

Not ten.
One or two.

For each saved technique, make sure it has:

- a real name
- a real description
- useful tags
- a short note saying when to use it

That is how the system slowly turns into something intelligent for your own work.

## What TDPilot Is, After All The Changes

After the recent fixes and cleanup work, my honest reading is:

TDPilot is now clearly a real working TouchDesigner MCP, not a fake surface.

Its core value is not the raw number of tools.
Its core value is the workflow:

- inspect
- build
- verify
- snapshot
- remember

That is where it becomes faster, better, and smarter than normal manual trial-and-error.

The flashy parts are not the main point.
The repeatable loop is the main point.

## What I Would Tell A Friend

If a friend asked me whether to use TDPilot, I would say:

Use it if you want a serious TD assistant that can help you read patches faster, build structured changes, debug with evidence, and gradually build a reusable memory of what works.

Do not use it if you are expecting a magic robot that will design your whole project for you while you sit back.

The sweet spot is not autopilot.

The sweet spot is accelerated craftsmanship.

## A Very Practical First Month Plan

### Week 1

- use it only for inspection and explanation
- ask it to read old patches
- ask it to explain structures in plain language

### Week 2

- let it build small isolated chains
- always force error checks
- keep all work inside sandbox COMPs

### Week 3

- use snapshots before bigger edits
- start letting it help with cleanup and refactors
- save your first two or three reusable techniques

### Week 4

- begin using `td_memory_recall` before rebuilding known ideas
- build one small personal library of good patterns
- start treating TDPilot as part of your normal TD workflow

That is a realistic ramp.

## If You Only Remember Three Things

Remember these:

1. Inspect before editing.
2. Work in small batches.
3. Save only what is truly worth reusing.

If you do that, TDPilot stops being a gimmick and starts becoming genuinely useful.

## Where To Read Next

If this guide helped and you want the deeper version:

- read [MEMORY_GUIDE.md](./MEMORY_GUIDE.md) for the full memory-building workflow
- read [MANUAL.md](./MANUAL.md) for the production manual
