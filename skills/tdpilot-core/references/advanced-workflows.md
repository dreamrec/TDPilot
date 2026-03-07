# TDPilot Advanced Workflows

## Optimization Workflow

`td_optimize_visual` runs iterative parameter tuning with objective weights (-1.0 to 1.0):

- **brightness** — push exposure/gain/opacity up or down
- **contrast** — push contrast/gamma controls
- **complexity** — push noise/detail/feedback/blur
- **motion_rhythm** — push speed/frequency/phase
- **stability** — inversely affects risk params (feedback, gain, displace)

Safety profiles: `conservative` (0.5x step), `balanced` (1.0x), `aggressive` (1.5x). Auto-stops on instability (pauses timeline) and on convergence.

## Safety System

- `td_set_param_bounds` — min/max limits enforced on every `td_set_params` call
- `td_detect_instability` — checks FPS < 30, error count, heavy node count
- `td_emergency_stabilize` — pauses timeline + applies stabilization
- Use bounds before optimization or experimental parameter sweeps

## Snapshots — Before/After

- `td_snapshot_scene` — captures full state
- `td_diff_snapshots` — compare what changed
- `td_restore_snapshot` — rollback (partial filters, dry-run supported)
- Always snapshot before major changes

## Events & Real-Time Monitoring

- Subscribe to `par_change`, `chop_change`, `cook_complete`, `node_error`, `timeline`
- Monitor TOPs with `td_monitor_visual` (metadata-only by default)
- Stream TOP frames with `td_stream_top`
- Events buffered (default 1000), retrieved with `td_get_events`

## Musical Timescale

`td_get_timescale_state` provides BPM-synced timing:

- Beat/bar/phrase(8-bar)/section(32-bar)/arc(128-bar) phases
- Countdown to next beat, bar, phrase
- Arc stage: intro → build → plateau → release
- Health metrics: tempo health, plateau risk, collapse risk

## Reference Architecture: Feedback-Displacement Fluid Texture ("Mountains Breath")

A proven recipe for BW fluid, feedback-displacement organic textures.

### Core Concept

Noise heightfield composited with texture, run through feedback loop with normal-map displacement. Edge detection + slope produces normals that drive displacement, creating self-referential fluid motion. Rendered as point cloud.

### Signal Flow

```
TERRAIN: noise5(simplex3d) → null10 (hub)
TEXTURE: noise7(random) → comp5(multiply) → null6
FEEDBACK: null6 → level4 → over2 → displace2 → null7
NORMALS: level1 → blur6, edge1 → blur5, select2 → comp3 → slope1 → blur3
ASSEMBLY: UV + select3 → rectangle3 → reorder1 → pointtransform1 → pos
RENDER: pos → pointRender(camera, light, bloom, DOF) → moviefileout1
```

### Key Parameter Recipes

**Terrain**: simplex3d, period=1.0-2.0, amp=0.47-0.49, offset=0.041, exponent=0.81-0.9, harmonics=0, scroll=0.3 (via absTime.seconds)

**Feedback Loop**: trail opacity=0.0055 (extremely low = long ghostly trails), clamp low=0.174-0.245, clamp high=0.712, displace weight X/Y=0.1, blur=4, extend=mirror

**Critical insight**: Feedback opacity at 0.0055 creates slow-evolving fluid look. Clamp range (0.174–0.712) is the "living zone" preventing collapse or blowout.

**Render**: pointsize=0.1, bloom=0.705-1.3, bloom intensity=0.12-0.74, DOF white=3.6-6.0

### Master Control Pattern

baseCOMP `master_ctrl` with 7 pages: Terrain, Feedback, Texture, Render, Camera, Object, Light. Each has reset pulse buttons. Wire with `op('/project1/master_ctrl').par.X.eval()` from inside COMPs.

### Color Coding

Green=(0.2,0.65,0.3) Terrain | Purple=(0.55,0.25,0.7) Texture | Orange=(0.85,0.45,0.1) Feedback | Blue=(0.2,0.45,0.8) Normals | Cyan=(0.1,0.65,0.7) Points | Red=(0.85,0.2,0.2) Render | Yellow=(0.9,0.75,0.15) Controls | Gray=(0.4,0.4,0.4) Infra
