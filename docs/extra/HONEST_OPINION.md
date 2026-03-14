# Honest Opinion On TDPilot

## The Honest Short Answer

I like it.

I think it is much more real than most "AI tool for creative coding" projects.

I also think it tries to do too many things at once in the product story.

Those two things are both true.

## What I Respect About It

The repo shows real effort in the right places:

- the TouchDesigner-side bridge is not a toy
- the tool surface is broad and mostly coherent
- memory is treated as a first-class concept
- there is real test coverage
- there is an attempt to turn vague AI behavior into repeatable workflow

That last part matters a lot.

Many tools in this space are basically:

- one or two scripts
- a demo video
- vague claims

TDPilot is not that.

It is an actual system.

## My Main Criticism

The product narrative leans too hard on tool count.

"86 tools" sounds impressive, but it is not where the durable value comes from.

The durable value comes from:

- reliable inspection
- safe incremental editing
- memory capture
- reuse
- validated workflow habits

If I were positioning this tool, I would emphasize:

"AI-assisted TouchDesigner workflow with reusable technique memory."

That is stronger than:

"Huge tool surface."

## Is It Too Much?

Yes and no.

### Yes, in presentation

For a normal TD user, 86 tools is too much to mentally model.

It creates a few risks:

- tool anxiety
- unclear starting point
- overpromising
- edge features getting shipped before core UX is simplified

### No, in architecture

Internally, a broad surface is not bad if:

- the core few workflows are clearly prioritized
- the rest are optional
- the user is not expected to memorize everything

That is the key distinction.

## Where The Real Value Will Come From

If this project becomes genuinely important, it will not be because it can call every possible TD function.

It will be because it helps people build a memory-backed TD workflow.

That means:

- inspect current patch fast
- build known-good subnet patterns faster
- learn from successful experiments
- replay and adapt proven building blocks
- keep a local library of what works for a team or studio

That is the real moat.

Not raw tool count.

## What Feels Extra

These feel less central to me:

- trying to make planning a headline feature too early
- very broad "native TD 2025 inspection" as a product pillar
- optimization language that sounds more autonomous than the current trust level supports
- surfaces that are registered and documented before they are battle-hardened

I would not delete them all.

But I would absolutely demote them in the product hierarchy.

## What I Would Focus On Instead

If I had to focus the next version, I would push hard on five things:

1. Core reliability
   Make the core 20 tools feel rock-solid.

2. Memory quality
   Better tags, notes, compatibility, validation, and replay confidence.

3. Curation workflow
   Make it easy to turn working subnet patterns into reusable assets.

4. User education
   Teach people how to use the system in a sane workflow.

5. Claim discipline
   Tight alignment between docs, tests, and reality.

## Would I Have Built It Differently?

Yes, a little.

I would have organized the public story around three layers:

1. Core TD Copilot
   inspect, build, parameterize, debug

2. Reuse Layer
   learn, save, recall, replay, preferences

3. Advanced Layer
   planning, optimization, TD-native introspection, monitoring

That would make the whole project easier to understand and trust.

## Do I Think It Is Worth Continuing?

Absolutely, yes.

Why:

- the base concept is strong
- the implementation already has substance
- TouchDesigner is exactly the kind of environment where AI becomes much more useful when it has real tools and memory
- reusable subnet memory is a genuinely valuable idea

## My Bottom-Line Product Opinion

TDPilot is best when it acts like:

- a disciplined TD assistant
- a reusable technique librarian
- a debugging and scaffolding copilot

TDPilot is weaker when it tries to sound like:

- a fully autonomous TD designer
- a universal TD intelligence layer
- a complete replacement for real TD decision-making

So my honest opinion is:

Keep it.
Use it.
Trust the core.
Supervise the advanced parts.
Invest heavily in memory and curation.
Trim the hype around the long tail.
