# What these TDPilot updates bring

MCP SDK 2 modernizes the connection between Codex and TDPilot. Native TD
transactions provide the improvement in recovery safety; the SDK alone does
not undo a failed edit.

| Change | Benefit |
| --- | --- |
| Updated dependencies | Patched dependency floors and a refreshed, reproducible lockfile. |
| TouchDesigner 2025.33230 support | Reviewed parameter names and knowledge for Time Filter POP, Nuitrack and native Gaussian-splat loading. Hardware-dependent Nuitrack tracking still needs a sensor test. |
| Bounded controls | Camera, material, particle and noise bindings can map incoming signals into explicit limits. |
| Smaller tool profiles | Optional inspection/build profiles reduce tool context while retaining the full default surface. |
| Panel and launcher fixes | Clearer live status and reliable selection of the intended installation. |
| Native atomic transactions | A typed patch executes in one TD callback and one owned undo block. |
| Verified rollback | Restores and compares affected graph state, including DAT content; refuses to undo intervening edits. |
| MCP SDK 2.3 | Newer protocol compatibility, stronger validation and explicit request context/cancellation handling. |

SDK 2 supports the newer 2026 protocol and older clients on the same server.
It runs synchronous handlers in worker threads and validates protocol results
more strictly. TDPilot continues to perform TD edits through its main-thread
HTTP callback. See the [official SDK overview](https://py.sdk.modelcontextprotocol.io/whats-new/)
and [2.3.0 release notes](https://github.com/modelcontextprotocol/python-sdk/releases/tag/v2.3.0).

Cancellation means the caller stopped waiting; a TD callback may already have
started. TDPilot needs a transaction receipt and bounded recovery handling to
resolve that outcome. See the [SDK cancellation guide](https://py.sdk.modelcontextprotocol.io/handlers/cancellation/).

Rollback safety means: if an edit changes five things and the fourth fails,
restore the previous affected state, check the restoration, and preserve work
performed separately. TD closes unfinished undo blocks at callback return, so
sending separate start/edit/end HTTP calls cannot provide that guarantee.
See [TouchDesigner Undo Class](https://derivative.ca/UserGuide/Undo_Class).

Qualification results belong to the individual release reports. The 2.5
baseline recorded 2,276 tests and 102 golden cases; those numbers do not by
themselves qualify the later transaction engine or SDK migration.
