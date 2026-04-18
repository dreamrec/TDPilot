# TDPilot Security and Threat Model

TDPilot executes AI-driven instructions inside a running TouchDesigner session.
That is inherently a sensitive position. This document covers what we do
protect against, and what we honestly do not.

## Architecture

```
MCP client  ── stdio ──>  MCP server  ── HTTP POST ──>  TouchDesigner
(Claude)                  (uv run)     (127.0.0.1)      WebServer DAT + callbacks
```

Both legs speak JSON; the TD-side callback file is what actually runs code.

## Enforcement layers

When you call `td_exec_python`:

1. **Client token scan** - fast substring match against a blocklist. Defeatable
   by string concatenation, so it is never the authority.
2. **Client AST scan** - parses the code with `ast.parse` and rejects any
   import/call/attribute/subscript nodes that touch dangerous builtins or
   modules. Catches the string-concat bypasses that layer 1 misses.
3. **Server env gate** - the TD callbacks file refuses to serve when
   `TD_MCP_SHARED_SECRET` is empty AND `TD_MCP_REQUIRE_AUTH=1` (the default).
   Installers always generate a secret. Secrets are compared in constant time.
4. **Server CORS / Sec-Fetch-Site** - rejects cross-site browser fetches.
   `Access-Control-Allow-Origin: *` is never emitted.
5. **Server token and AST scan** - same policy as the client, duplicated so a
   malicious MCP server implementation cannot bypass the TD-side check.
6. **Sandboxed globals** - restricted and standard modes run user code with a
   custom `__builtins__` dict that omits the dangerous builtins.

## Exec modes

| Mode | Default | Imports | Builtins | TD API | Intended for |
|---|---|---|---|---|---|
| off | no | - | - | - | Read-only MCP clients |
| restricted | yes | blocked | curated (no getattr/hasattr/type) | read-only | Default agent loop |
| standard | no | 14 whitelisted (json, math, re, ...) | curated | mutating | Agent loop with safe helpers |
| full | no | unrestricted | unrestricted | unrestricted | Developer sessions only |

## What we do NOT protect against

**1. A compromised MCP client.** The MCP server trusts the process that
invoked it over stdio. If your Claude client is malicious, TDPilot has no
way to know.

**2. Code stashed in a Text DAT and then called via `mod.<dat>`.**
Restricted mode now blocks `.text = ...` writes and `create(textDAT)` calls,
but a creative caller might still construct DAT content via allowed
operators. If you rely on restricted mode as a hard boundary, audit the
project's existing DATs — they become part of the attack surface.

**3. Exhaustion attacks (CPU, GPU, memory).** There is a 30-second timeout
but no per-client quota. A runaway LLM can burn frames or load a huge TOP.

**4. Filesystem reads via TD's native operators.** File In DATs, Movie File
In TOPs, and similar can read any file readable by the TD process.
Restricted mode blocks setting `.par.file` dynamically, but pre-wired
operators are untouched. Mitigate by running TD as a user without access to
sensitive files.

**5. Network calls from TD's native operators.** Web Client DATs, WebSocket
DATs, OSC In/Out CHOPs — none are gated by exec mode. Mitigate at the OS or
network layer.

## Threat-model posture

TDPilot is designed for local single-user sessions where you trust the AI
client (Claude Desktop, Claude Code, and similar). It is NOT designed to be
multi-tenant or internet-exposed. If you need that, put TDPilot behind a
reverse proxy with real auth and treat exec mode as `off`.

## Reporting

Open an issue at https://github.com/dreamrec/TDPilot/issues with a
`security:` prefix, or contact the maintainer for confidential disclosure.
