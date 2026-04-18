# Building Preset Systems, Custom Controls & Morphing UI in TouchDesigner

A reference for building production-grade preset management, parameter morphing, custom UI widgets, and scene-launching systems in TouchDesigner — using only native TD capabilities and Python extensions.

---

## 1. Architecture: Model-View-Controller for Presets

The most robust approach separates concerns into three tiers:

### Tier 1 — Preset Engine (Model, no UI)

A standalone COMP with an extension class (`extPresetEngine`) that handles:
- Storing/loading preset dictionaries
- Interpolation between states
- Random value generation
- JSON import/export

**Why separate?** The engine can be reused headlessly — in installations, automated shows, or batch rendering — without any UI overhead.

### Tier 2 — Parameter UI (Controller + View)

A COMP that creates interactive slider/toggle/menu widgets, binds them to real operator parameters, and delegates all preset logic to the engine.

### Tier 3 — Scene/Cue Launcher (Show Control)

A performance layer that treats presets as "scenes" with duration, delay, transition curve, follow-actions (next/repeat/random), and scripted triggers.

**Key principle:** Each tier references the one below it but never above. The engine knows nothing about UI. The UI knows nothing about scenes.

---

## 2. Persistent State with TDStoreTools

The foundation of any preset system in TD is `TDStoreTools.StorageManager` — it creates Python dictionaries that survive project save/load cycles.

### Setup Pattern

```python
# In an extension class __init__
from TDStoreTools import StorageManager

storedItems = [
    {'name': 'Presets',             'default': {},    'dependable': True},
    {'name': 'CurrentPresetName',   'default': '',    'dependable': True},
    {'name': 'MorphTime',           'default': 2.0,   'dependable': True},
    {'name': 'MorphCurve',          'default': 'linear', 'dependable': True},
    {'name': 'Locked',              'default': False, 'dependable': True},
]
self.stored = StorageManager(self, ownerComp, storedItems)
```

### Why This Matters
- `dependable=True` means changes to these dictionaries trigger cooking downstream — any DAT or expression watching them auto-updates.
- The data lives in the `.toe` file itself, no external files needed.
- You can still export/import JSON for portability.

### Access Pattern
```python
# Store
self.stored['Presets']['myPreset'] = self._captureState()

# Retrieve raw dict (bypass dependable wrapper)
state = self.stored['Presets'].getRaw()['myPreset']

# Export to JSON
import json
json.dumps(self.stored['Presets'].getRaw(), indent=2)
```

---

## 3. Capturing and Restoring Operator State

### State Capture

To snapshot an operator's parameters:

```python
def captureState(self, operators):
    """Capture current parameter values from a list of operator paths."""
    state = {}
    for opPath in operators:
        target = op(opPath)
        if target is None:
            continue
        state[opPath] = {}
        for p in target.pars():
            # Skip read-only, non-saveable, pulse, and header params
            if p.readOnly or not p.saveable or p.isPulse:
                continue
            state[opPath][p.name] = {
                'val':  p.eval_val(),  # use .eval() in TD
                'min':  p.min if hasattr(p, 'min') else None,
                'max':  p.max if hasattr(p, 'max') else None,
                'type': p.style,  # Float, Int, Toggle, Menu, etc.
            }
    return state
```

### State Restoration (Immediate)

```python
def restoreState(self, state):
    """Jump to a preset state immediately."""
    for opPath, params in state.items():
        target = op(opPath)
        if target is None:
            continue
        for pName, pData in params.items():
            par = getattr(target.par, pName, None)
            if par and not par.readOnly:
                par.val = pData['val']
```

### Essential vs Full State

For interpolation, you only need `{opPath: {paramName: value}}` (the "essential state"). The full state with min/max/type is for UI reconstruction and validation.

---

## 4. Morphing / Interpolation Between Presets

### CPU-Based Frame-Sync Interpolation

GPU-based interpolation (via TOPs) introduces latency. For frame-accurate parameter morphing, use a Timer CHOP or `absTime.frame` with a Python callback:

```python
def morphStep(self, progress):
    """Called each frame during a morph. progress: 0.0 to 1.0"""
    t = self._applyCurve(progress, self.morphCurve)
    for opPath in self.sourceState:
        target = op(opPath)
        for pName in self.sourceState[opPath]:
            src = self.sourceState[opPath][pName]
            dst = self.targetState[opPath][pName]
            pType = self.fullState[opPath][pName].get('type', 'Float')

            if pType in ('Float', 'Int'):
                # Continuous interpolation
                val = src + (dst - src) * t
                if pType == 'Int':
                    val = round(val)
            elif pType in ('Toggle', 'Menu'):
                # Discrete: switch at midpoint (or start/end)
                val = dst if t > 0.5 else src
            else:
                val = dst if t >= 1.0 else src

            par = getattr(target.par, pName, None)
            if par:
                par.val = val
```

### Timer CHOP Pattern

Use a Timer CHOP to drive morph progress:
1. Set Timer length to morph duration
2. Read `timer_fraction` channel (0 to 1)
3. Feed into Python callback via CHOP Execute DAT

```
Timer CHOP (morphTimer)
  length = morphTime seconds
  play = triggered on morph start
  timer_fraction --> chopexec callback --> morphStep(fraction)
```

### Easing / Curve Functions

Common easing functions (pure Python, no dependencies):

```python
import math

def easeInOut(t):
    """Smooth acceleration and deceleration (Hermite smoothstep)."""
    return t * t * (3 - 2 * t)

def easeIn(t):
    return t * t

def easeOut(t):
    return 1 - (1 - t) ** 2

def easeInOutCubic(t):
    return 4 * t**3 if t < 0.5 else 1 - (-2*t + 2)**3 / 2

def snapIn(t):
    """Stay near start, snap to end."""
    return t ** 4

def snapOut(t):
    """Jump to near-end quickly, ease into final."""
    return 1 - (1 - t) ** 4

def exponential(t):
    return (math.exp(t * 3) - 1) / (math.e**3 - 1)

CURVES = {
    'linear': lambda t: t,
    'easeIn': easeIn,
    'easeOut': easeOut,
    'easeInOut': easeInOut,
    'easeInOutCubic': easeInOutCubic,
    'snapIn': snapIn,
    'snapOut': snapOut,
    'exponential': exponential,
}
```

---

## 5. Random Value Generation with Distributions

Different distributions produce very different aesthetic results:

```python
import random
import math

def uniformRandom(minVal, maxVal):
    return random.uniform(minVal, maxVal)

def gaussianRandom(minVal, maxVal, sigma=0.25):
    """Bell-curve centered in range. sigma controls spread."""
    center = (minVal + maxVal) / 2
    spread = (maxVal - minVal) / 2
    val = random.gauss(0, sigma) * spread + center
    return max(minVal, min(maxVal, val))

def binaryRandom(minVal, maxVal):
    """Only min or max, nothing between."""
    return random.choice([minVal, maxVal])

def brownianStep(currentVal, minVal, maxVal, stepSize=0.1):
    """Random walk from current value."""
    delta = random.uniform(-stepSize, stepSize) * (maxVal - minVal)
    return max(minVal, min(maxVal, currentVal + delta))

DISTRIBUTIONS = {
    'uniform':   uniformRandom,
    'gaussian':  gaussianRandom,
    'binary':    binaryRandom,
}
```

### Per-Parameter Control

The power move: let each parameter have its own distribution, range override, and lock state. A locked parameter stays fixed during randomization — essential for keeping structure while varying texture.

---

## 6. Algorithmic Pattern Generators (SuperCollider-Style)

These generator patterns produce deterministic or probabilistic sequences, useful for preset sequencing or per-parameter modulation:

```python
class Pseq:
    """Sequential pattern — cycles through a list."""
    def __init__(self, sequence, repeats=float('inf'), offset=0):
        self.seq = sequence
        self.repeats = repeats
        self.idx = offset
        self.cycles = 0

    def next(self):
        if self.cycles >= self.repeats:
            return None
        val = self.seq[self.idx % len(self.seq)]
        self.idx += 1
        if self.idx % len(self.seq) == 0:
            self.cycles += 1
        return val

class Pbrown:
    """Brownian motion — random walk within bounds."""
    def __init__(self, lo=0, hi=1, step=0.1, length=float('inf')):
        self.lo, self.hi, self.step = lo, hi, step
        self.length = length
        self.val = (lo + hi) / 2
        self.count = 0

    def next(self):
        if self.count >= self.length:
            return None
        self.val += random.uniform(-self.step, self.step)
        self.val = max(self.lo, min(self.hi, self.val))
        self.count += 1
        return self.val

class Pwhite:
    """White noise — uniform random."""
    def __init__(self, lo=0, hi=1, length=float('inf')):
        self.lo, self.hi = lo, hi
        self.length = length
        self.count = 0

    def next(self):
        if self.count >= self.length:
            return None
        self.count += 1
        return random.uniform(self.lo, self.hi)

class Pwrand:
    """Weighted random selection."""
    def __init__(self, sequence, weights, repeats=float('inf')):
        self.seq = sequence
        self.weights = weights
        self.repeats = repeats
        self.count = 0

    def next(self):
        if self.count >= self.repeats:
            return None
        self.count += 1
        return random.choices(self.seq, weights=self.weights, k=1)[0]

class Pxrand:
    """Random selection, never repeating consecutively."""
    def __init__(self, sequence, repeats=float('inf')):
        self.seq = sequence
        self.repeats = repeats
        self.count = 0
        self.last = None

    def next(self):
        if self.count >= self.repeats:
            return None
        choices = [x for x in self.seq if x != self.last]
        if not choices:
            choices = self.seq
        val = random.choice(choices)
        self.last = val
        self.count += 1
        return val
```

**Use case:** Assign a `Pbrown` to feedback opacity for slow organic drift, a `Pxrand` to color palette index for variety without repetition, a `Pseq` to camera angles for rhythmic switching.

---

## 7. Building Custom UI Widgets in TouchDesigner

### Widget Architecture

Each UI element is a Container COMP with:
- A slider/button/toggle visual (usually a Container + TOP for rendering)
- Custom parameters for `Value`, `Min`, `Max`, `Label`, `Locked`
- An extension class handling mouse interaction
- Callbacks: `OnValueChange`, `OffToOn`, `OnToOff`

### Slider Widget Pattern

```
Container COMP "slider_float"
  bg         (Constant TOP — background bar)
  fill       (Constant TOP — value fill, width = value/range * parent.width)
  label      (Text TOP — parameter name)
  valueDisp  (Text TOP — current numeric value)
  Panel CHOP Execute DAT — handles mouse drag
  Extension: extSliderWidget
       .Value   (property, clamped to range)
       .Range   (property, (min, max) tuple)
       .Locked  (property, prevents editing)
       OnValueChange(callback)
```

### Mouse Interaction Pattern

```python
# In Panel Execute DAT — handling click-drag on a slider
def onPanelEvent(panelValue):
    if panelValue.name == 'lselect' and panelValue.val:
        # Start drag
        parent().store('dragging', True)

    if parent().fetch('dragging', False):
        # Map mouse U (0-1) to parameter range
        u = parent().panel.u.val
        ext = parent().ext.SliderWidget
        newVal = ext.Range[0] + u * (ext.Range[1] - ext.Range[0])
        ext.Value = newVal

    if panelValue.name == 'lselect' and not panelValue.val:
        parent().store('dragging', False)
```

### Dynamic Container Layout

```python
def updateLayout(container, elements, spacing=5, elementHeight=30):
    """Stack elements vertically with consistent spacing."""
    y = 0
    for elem in elements:
        elem.par.y = y
        elem.par.h = elementHeight
        elem.par.w = container.par.w
        y += elementHeight + spacing
    container.par.h = y
```

### Expert Mode Pattern

Show/hide advanced controls (per-element timing, distribution, LFO settings) behind a toggle. Default view shows just sliders + preset buttons. Expert mode reveals the full control surface.

---

## 8. Preset Button UI Pattern

### Visual Preset Slots

Create a row of button COMPs, one per preset slot:

```python
def spawnPresetButton(parent, index, x):
    btn = parent.create(containerCOMP, f'preset_{index}')
    btn.par.x = x
    btn.par.w = 40
    btn.par.h = 30
    # Color indicates state
    btn.color = (0.3, 0.3, 0.3)  # Empty
    return btn

def updateButtonColor(btn, hasData, isActive):
    if isActive:
        btn.color = (0.2, 0.7, 0.3)   # Active preset — green
    elif hasData:
        btn.color = (0.5, 0.5, 0.6)   # Stored — light
    else:
        btn.color = (0.3, 0.3, 0.3)   # Empty — dark
```

### Modifier-Click Actions

A compact interaction scheme using keyboard modifiers:

| Action | Modifier | Effect |
|--------|----------|--------|
| Recall | Click | Morph to preset |
| Jump | Ctrl+Click | Instant jump (no interpolation) |
| Store | Shift+Click | Save current state |
| Delete | Shift+Right-Click | Clear slot |
| Freeze | Shift+Middle-Click | Lock preset from edits |

### Drag-and-Drop Reordering

```python
def onDrop(source, target):
    """Swap preset data between two slots."""
    presets = engine.stored['Presets']
    srcData = presets.get(source.name)
    dstData = presets.get(target.name)
    presets[source.name] = dstData
    presets[target.name] = srcData
    refreshButtons()
```

---

## 9. Arbitrary Preset Blending

Beyond morphing A to B over time, expose a continuous `Blend` parameter (0.0 to 1.0) between any two named presets:

```python
def blendPresets(self, presetA, presetB, blend):
    """Blend between two presets. blend=0 is A, blend=1 is B."""
    stateA = self.stored['Presets'][presetA]
    stateB = self.stored['Presets'][presetB]

    for opPath in stateA:
        target = op(opPath)
        if target is None:
            continue
        for pName in stateA[opPath]:
            a = stateA[opPath][pName]
            b = stateB[opPath].get(pName, a)
            if isinstance(a, (int, float)):
                val = a + (b - a) * blend
                setattr(target.par, pName, val)
```

**Use case:** Map blend to a MIDI fader, a CHOP LFO, or mouse position for real-time preset crossfading.

---

## 10. Scene/Cue Launcher Architecture

### Scene Data Structure

```python
scene = {
    'name':         'intro',
    'preset':       'warm_abstract',    # target preset name
    'duration':     4.0,                # morph time in seconds
    'delay':        0.0,                # wait before starting
    'curve':        'easeInOut',        # interpolation curve
    'followAction': 'next',             # none | next | repeat | random
    'script':       '',                 # Python to execute on trigger
    'color':        (0.2, 0.4, 0.8),   # UI color coding
}
```

### Follow Actions

After a scene completes:
- **none** — stop
- **next** — trigger the next scene in list
- **repeat** — replay this scene
- **random** — pick a random scene (optionally weighted)

This enables fully automated generative performances.

### Musical Timing Integration

Instead of seconds, express durations in beats/bars:

```python
def beatsToSeconds(beats, bpm):
    return beats * 60.0 / bpm

def barsToSeconds(bars, bpm, beatsPerBar=4):
    return bars * beatsPerBar * 60.0 / bpm
```

Connect to TD's Beat CHOP or Ableton Link for synchronized transitions.

### Animation Export

Convert a sequence of scenes into a TD Animation COMP:

```python
def scenesToAnimation(scenes, animComp):
    """Create keyframes from scene sequence."""
    time = 0
    for scene in scenes:
        time += scene.get('delay', 0)
        preset = getPreset(scene['preset'])
        for opPath, params in preset.items():
            for pName, val in params.items():
                chanName = f"{opPath}/{pName}"
                # Create keyframe at current time
                animComp.insertKey(chanName, time, val)
        time += scene['duration']
```

---

## 11. MIDI/OSC Auto-Learn Mapping

### Auto-Learn Pattern

```python
class MIDIMapper:
    def __init__(self):
        self.mappings = {}      # {midiCC: paramPath}
        self.learning = False
        self.learnTarget = None

    def startLearn(self, paramPath):
        """Activate learn mode — next MIDI input gets mapped."""
        self.learning = True
        self.learnTarget = paramPath

    def onMIDI(self, channel, cc, value):
        """Called from MIDI In CHOP Execute."""
        if self.learning:
            self.mappings[cc] = self.learnTarget
            self.learning = False
            self.learnTarget = None
            return

        if cc in self.mappings:
            paramPath = self.mappings[cc]
            # Remap 0-127 to parameter range
            parts = paramPath.rsplit('/', 1)
            target = op(parts[0])
            par = getattr(target.par, parts[1])
            normalized = value / 127.0
            par.val = par.normMin + normalized * (par.normMax - par.normMin)
```

### Bidirectional Feedback

For motorized faders or LED rings, send values back:
```python
def sendFeedback(self, cc, paramValue, paramMin, paramMax):
    normalized = (paramValue - paramMin) / (paramMax - paramMin)
    midiVal = int(normalized * 127)
    op('midiout1').sendControl(0, cc, midiVal)
```

---

## 12. Performance Optimization Tricks

### Dictionary-First Lookups

Replace `getattr(op, 'par')` chains with pre-cached dictionaries for hot paths:

```python
# Slow (every frame during morph):
val = getattr(op(path).par, name)

# Fast (cache references once):
self._parCache = {}
for opPath in operators:
    self._parCache[opPath] = {}
    for p in op(opPath).pars():
        self._parCache[opPath][p.name] = p

# Then in hot loop:
self._parCache[opPath][name].val = newValue
```

### Perform Mode

After preset setup is complete, strip UI overhead for live performance:
- Disable cooking on UI containers (`.allowCooking = False`)
- Collapse panel viewers
- Use CHOP exports instead of expressions for parameter bindings

### Channel Export vs Expressions

For high-frequency updates (morphing every frame), CHOP exports are faster than Python parameter writes. Consider exposing morph targets as CHOP channels:

```
Timer CHOP -> Math (curve shape) -> Merge -> CHOP Export to target parameters
```

---

## 13. Master Control COMP Pattern

For complex projects, centralize control parameters:

```python
# Create a baseCOMP with custom parameter pages
# Page: Global — morphTime, morphCurve, distribution, masterLock
# Page: Terrain — freq, amp, offset, harmonics, seed
# Page: Feedback — opacity, clamp, blur, displacement
# Page: Render — pointSize, bloom, DOF, exposure

# Wire everything via expressions:
# op('noise1').par.amp.expr = "op('/project1/controls').par.Amp"
# This gives you one place to control the entire project
```

### Reset Pulse Buttons

Add pulse parameters per-page that reset all values to defaults:

```python
def onPulse(par):
    if par.name.startswith('Reset'):
        page = par.page
        for p in page.pars:
            if p.name != par.name and p.default is not None:
                p.val = p.default
```

---

## 14. JSON Import/Export for Portability

### Export with Metadata

```python
def exportPresets(self, filepath):
    import json, datetime
    data = {
        'version': '1.0',
        'created': datetime.datetime.now().isoformat(),
        'morphTime': self.stored['MorphTime'],
        'morphCurve': self.stored['MorphCurve'],
        'presets': self.stored['Presets'].getRaw(),
        'bindings': self._getBindings(),  # Which ops are connected
    }
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)
```

### Import with Validation

```python
def importPresets(self, filepath):
    import json
    with open(filepath, 'r') as f:
        data = json.load(f)

    # Validate operator paths still exist
    for presetName, state in data['presets'].items():
        for opPath in list(state.keys()):
            if op(opPath) is None:
                debug(f"Warning: {opPath} not found, skipping")
                del state[opPath]

    self.stored['Presets'].update(data['presets'])
```

---

## 15. Binding System — Connecting UI to Parameters

### Path-Based Bindings

Maintain a mapping of UI elements to operator parameters:

```python
# Binding data structure
binding = {
    'elementName': 'slider_opacity',
    'targetOp':    '/project1/feedback/level1',
    'targetPar':   'opacity',
    'dataSource':  'parameter',   # or 'channel' for CHOP data
}

# Binding table (stored in DAT for persistence)
# Name | TargetOp | TargetPar | DataSource
```

### Wildcard Parameter Capture

When adding an operator to the UI, use wildcards to auto-capture relevant parameters:

```python
import re

def captureParams(opPath, pattern='*'):
    """Capture parameters matching a wildcard/regex pattern."""
    target = op(opPath)
    regex = re.compile(pattern.replace('*', '.*'))
    return [p for p in target.pars()
            if regex.match(p.name) and not p.readOnly and p.saveable]
```

This lets users add `noise1` with pattern `freq*|amp*` to only capture frequency and amplitude params.

---

## Summary: Building Blocks Checklist

When building a preset/morphing system in TD:

- Extension class with `TDStoreTools.StorageManager` for persistent state
- State capture: snapshot operator parameters into dictionaries
- State restore: immediate jump to a stored state
- Morphing: Timer CHOP driving frame-by-frame interpolation with easing curves
- Random: Multiple distributions (uniform, gaussian, binary, brownian)
- Per-parameter control: individual lock, range, distribution, timing
- Discrete handling: toggles/menus switch at threshold, not interpolate
- Preset buttons: visual slots with modifier-click actions
- Blend: continuous 0-1 crossfade between any two presets
- Scene launcher: presets + duration + delay + follow actions
- Musical timing: beat/bar quantization via Beat CHOP
- MIDI/OSC: auto-learn mapping with range remapping
- JSON export/import: portable preset files with metadata
- Master control COMP: centralized parameter pages
- Performance mode: disable UI cooking for live shows
- Pattern generators: Pseq, Pbrown, Pwhite for algorithmic variation
- Binding system: wildcard/regex parameter capture with path management
