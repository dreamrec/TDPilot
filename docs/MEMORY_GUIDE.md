# How To Build TDPilot's Memory And Brain

This is the most important manual in this folder.

Why:

Because the real long-term value of TDPilot is not the tool count.

It is the memory.

## First: What "Memory" Means In TDPilot

TDPilot does not automatically become smart because you installed it.

Its "brain" is made from four layers:

1. Live project context
   What the AI can inspect in the current TouchDesigner session.

2. Local docs corpus
   Built-in knowledge cards for operators, palette components, snippets, and release notes.

3. Technique memory
   Saved subnet recipes learned from real TD projects.

4. Preference memory
   Saved team or user defaults such as naming, layout, and preferred patterns.

That means the "brain" is partly built-in, but mostly curated.

## What You Should Actually Try To Build

Do not try to create a giant blob of random knowledge.

Build a useful working memory library instead.

The goal is:

- reusable
- searchable
- proven
- small enough to trust

The best memory library is not the biggest one.

It is the one that contains patterns you actually use again.

## The Four Memory Inputs You Need

### 1. Your own successful subnet patterns

This is the best source.

Examples:

- feedback cores
- audio-reactive control chains
- displacement stacks
- control COMPs
- parameter pages
- stable scene switchers
- debug / diagnostics helpers

If it worked in a real project, it is a candidate.

### 2. Official TouchDesigner examples

Use:

- OP Snippets
- Palette components
- TouchDesigner Curriculum examples
- official docs pages

Then rebuild the useful part cleanly in your own project and save that version.

Do not save giant official examples blindly.

Distill them.

### 3. Trusted tutorials

Good tutorial sources:

- official tutorials index:
  <https://docs.derivative.ca/Tutorials>
- Learn TouchDesigner:
  <https://docs.derivative.ca/Learn_TouchDesigner>
- OP Snippets:
  <https://docs.derivative.ca/OP_Snippets>

You can also learn from respected community sources listed on the official tutorials page, but always distill them into your own tested subnet before saving to memory.

### 4. Your team's preferences

Examples:

- naming conventions
- favorite operators
- preferred resolutions
- default control pages
- color coding rules
- "safe" starter patterns

These belong in `td_memory_preferences`.

## What Not To Put In Memory

Do not save:

- unfinished experiments
- giant messy networks
- unclear one-off hacks
- patterns you do not understand
- anything you cannot replay or explain
- tutorial copies with zero cleanup

That is not memory.

That is clutter.

## The Best Practical Workflow

Use this loop:

1. Build or improve something in TD.
2. Clean the subnet.
3. Validate it.
4. Learn it.
5. Save it with useful metadata.
6. Re-test by recalling or replaying.
7. Promote only after reuse.

That is how you grow a real brain.

## Step-by-Step Manual

### Step 1: Create a sandbox project

Make one project just for memory harvesting.

Use it to:

- rebuild tutorial ideas
- isolate useful patterns
- clean subnet structure
- test replayability

This keeps your production patch cleaner.

### Step 2: Give the project a memory namespace

Set:

```bash
export TDPILOT_PROJECT_NAME="your_project_name"
```

Why:

- project-scoped memory becomes persistent
- you avoid mixing everything into a global pile

You can also set `TDPILOT_MEMORY_DIR` if you want memory stored somewhere team-managed.

### Step 3: Distill a technique

Take one usable subnet.

Examples:

- a feedback core
- a beat-synced LFO driver
- a flexible level / blur / composite stack
- a reusable out TOP wrapper

Then ask the AI:

"Inspect `/project1/techniques/feedback_core`, summarize what it does, and tell me if this looks like a reusable technique."

If yes, continue.

### Step 4: Learn it

Use:

- `td_memory_learn`

What this gives you:

- complexity estimate
- recipe when the network is small/medium
- family/type summary
- required operator types
- metadata about the subnet

### Step 5: Save it properly

Use:

- `td_memory_save`

When you save, always provide:

- a real name
- a real description
- real tags
- notes

Good example:

- name:
  `feedback_color_smear_basic`
- description:
  `small reusable TOP feedback core with transform, level, and controlled decay`
- tags:
  `feedback`, `tops`, `stable`, `performant`, `reusable`
- notes:
  `best for small texture loops; safe at 1080p; expose decay and transform separately`

Bad example:

- name:
  `cool thing`
- tags:
  `art`, `nice`

## The Tagging System I Recommend

Use a simple structured tag style.

Tag categories:

- family:
  `tops`, `chops`, `comps`, `pops`, `sops`
- purpose:
  `feedback`, `audio-reactive`, `control-ui`, `mapping`, `debug`, `instancing`
- quality:
  `stable`, `portable`, `lightweight`, `high-cpu`, `validated`
- context:
  `show`, `installation`, `vj`, `lookdev`, `tools`

Example tag sets:

- `tops`, `feedback`, `stable`, `lightweight`
- `chops`, `audio-reactive`, `show`, `validated`
- `comps`, `control-ui`, `portable`, `tools`

## The Validation Ladder

Do not promote memory entries too early.

Use this ladder:

### Level 1: candidate

The subnet worked once.

### Level 2: validated local

It replayed or rebuilt cleanly in your current environment.

### Level 3: validated portable

It works in a different project or after cleanup.

### Level 4: global

It is worth sharing as a default building block.

That is the right promotion model.

## How To Learn From Official Docs And Tutorials

This is the best way to use external sources with TDPilot.

### Path A: official docs -> pattern

1. Look up the operator:
   `td_get_operator_doc`
2. Ask for parameter help on the live node:
   `td_get_param_help`
3. Find example snippets:
   `td_lookup_snippets`
4. Rebuild a small useful version.
5. Save your cleaned version as a technique.

### Path B: Palette -> reusable component knowledge

1. Search palette component:
   `td_lookup_palette_component`
2. Ask when it should be used.
3. Decide whether to use the palette component directly or build a simpler custom variant.
4. Save either:
   - a preferred usage note in preferences
   - or a cleaned technique in memory

### Path C: tutorial -> distilled subnet

1. Follow the tutorial.
2. Extract the smallest reusable part.
3. Clean names and layout.
4. Save notes about when to use it.
5. Learn and save it.

## The Preferences Layer

Technique memory is not enough.

You also want preference memory.

Examples to store:

- `naming.top_prefix = fx_`
- `naming.control_comp = ctrl`
- `resolution.default = 1920x1080`
- `layout.flow_direction = left_to_right`
- `palette.favorite_feedback = cacheTOP_loop`
- `style.prefer_palette_over_custom = false`

Store these with:

- `td_memory_preferences`

This helps the AI stop reinventing your working style every session.

## The Weekly Memory Routine

Do this once a week:

1. List techniques.
2. Remove junk.
3. Favorite the ones that helped.
4. Improve weak names and tags.
5. Promote only proven entries.
6. Add two or three preference keys based on repeated choices.

That one habit will improve the system more than adding 20 random entries.

## The Best Prompts For Building Memory

### Prompt 1: identify candidates

"Inspect `/project1/techniques` and tell me which subnets look like good reusable candidates for memory."

### Prompt 2: distill before save

"Inspect `/project1/sketch1/audio_driver` and suggest how to simplify it into a reusable memory entry before saving."

### Prompt 3: save correctly

"Learn the subnet at `/project1/techniques/lfo_driver`, then save it with a strong name, description, tags, and notes."

### Prompt 4: curate the library

"List my current project techniques and tell me which ones look redundant, under-described, or not worth promoting."

### Prompt 5: reuse memory

"Search the memory for a small stable feedback TOP technique, summarize the best match, and tell me whether replay or manual adaptation is safer."

## What The Brain Should Look Like After 30 Days

After a month, a good TDPilot memory library should contain:

- 10 to 25 real reusable techniques
- clear tag structure
- 5 to 15 useful preference keys
- a small set of favorites
- at least a few entries that were reused in a second project

That is enough to create compounding value.

## The Most Important Truth

TDPilot does not become smart by scraping everything.

It becomes smart by:

- collecting only the good patterns
- naming them well
- validating them
- reusing them
- updating them when your practice improves

That is how you build the brain.

## Useful External Sources For Feeding The Brain

- Learn TouchDesigner:
  <https://docs.derivative.ca/Learn_TouchDesigner>
- Official tutorials:
  <https://docs.derivative.ca/Tutorials>
- OP Snippets:
  <https://docs.derivative.ca/OP_Snippets>
- Palette:
  <https://docs.derivative.ca/Palette>
- TDResources:
  <https://docs.derivative.ca/TDResources>
- Project class:
  <https://docs.derivative.ca/Project_Class>
- COMP class:
  <https://docs.derivative.ca/COMP_Class>
- Page class:
  <https://docs.derivative.ca/Page_Class>
- MCP FAQ:
  <https://modelcontextprotocol.io/faqs>
