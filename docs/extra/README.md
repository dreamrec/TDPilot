# TDPilot Extra Docs

This folder contains a practical, opinionated documentation set for using TDPilot as a real TouchDesigner production tool, not just as a codebase.

Files:

- `MASTER_AUDIT.md` - final deep audit of what TDPilot is, what works well, what is still rough, and whether it is worth using.
- `MEDIOCRE_USER_MANUAL.md` - a practical guide for a mid-level TouchDesigner user who wants to leverage AI without getting lost.
- `HONEST_OPINION.md` - a blunt product critique: where the value is, what feels extra, and how I would trim or focus it.
- `MEMORY_BRAIN_MANUAL.md` - a concrete manual for building TDPilot's memory, knowledge habits, and reusable technique library.
- `WHAT_TO_FIX.md` - a prioritized roadmap of what should be fixed next, why it matters, and the order I would tackle it.

Suggested reading order:

1. `MASTER_AUDIT.md`
2. `MEDIOCRE_USER_MANUAL.md`
3. `MEMORY_BRAIN_MANUAL.md`
4. `HONEST_OPINION.md`
5. `WHAT_TO_FIX.md`

Audit basis:

- Local repo inspection and runtime review
- `uv run --extra dev pytest tests/ -q` -> 300 passed
- live TouchDesigner checks against build `2025.32460`
- public repo review at <https://github.com/dreamrec/TDPilot/tree/main>
- official TouchDesigner docs and curriculum links
- official MCP documentation
