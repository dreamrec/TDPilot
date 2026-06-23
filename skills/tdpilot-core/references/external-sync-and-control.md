# External Sync and Control: Ableton Link, MIDI, DAW Audio

Use this reference when the user wants TouchDesigner visuals to follow a DAW,
hardware sequencer, MIDI controller, or another performance system. The common
mistake is treating all "music sync" requests as audio-reactive work. There
are three distinct routes:

| User wants | Prefer |
| --- | --- |
| Spectrum or envelope visuals from a DAW | `audiostreaminCHOP` through a loopback or stream |
| Beat, bar, phase, or BPM sync with Ableton Live | Ableton Link path with `abletonlinkCHOP` |
| Hardware MIDI controls, notes, CCs, clock, or MTC | MIDI path with `midiinCHOP`, `midiinmapCHOP`, or `midiinDAT` |
| Send MIDI to a controller, synth, or lighting bridge | `midioutCHOP` |

Most AV performance systems combine routes: Link for tempo/phase, audio for
spectrum energy, and MIDI for performer gestures.

## DAW Audio Path

Use this for audio-reactive visuals where the waveform or spectrum is the
control source.

- macOS: route the DAW output to BlackHole, then select that stream in
  `audiostreaminCHOP`.
- Windows: use VB-Audio Cable or Voicemeeter.
- Cross-machine: use NDI audio into `audiostreaminCHOP`.

A typical chain is:

```text
audiostreaminCHOP -> audiofilterCHOP -> audiospectrumCHOP -> mathCHOP -> nullCHOP
```

This path has no symbolic knowledge of bars or beats. Add Ableton Link when the
visual needs phase or downbeat alignment.

## Ableton Link Path

Use `abletonlinkCHOP` when the visual system should lock to Ableton's shared
tempo, phase, bar, or beat without routing audio.

Create an `abletonlinkCHOP` and enable the Link session:

```text
active = 1
enable = 1
signature1 = 4
signature2 = 4
```

Then enable only the output channels the network consumes, such as `tempo`,
`beats`, `beat`, `phase`, `bar`, `rampbeat`, `rampbar`, `pulse`, and `status`.
The useful animation channels are usually `phase`, `rampbeat`, or `pulse`.

Ableton side:

- Live 12: Settings > Link > Show Link Toggle, then click Link in the transport.
- Live 11: Preferences > Link/Tempo/MIDI, then enable the Link toggle.

Windows warning: DirectX/MME drivers can hide or disable Ableton Link. Switch
Live to ASIO or ASIO4ALL before debugging the TouchDesigner side.

Network warning: Ableton Link peer discovery uses UDP multicast on group
224.76.78.75 port 20808. If `numpeers` stays at 0, check VPN routing, mobile
hotspot client isolation, firewall UDP 20808, Docker bridge networking, and
cross-subnet multicast routing.

There is no separate `quantum` output channel. Use `signature1` and
`signature2` for the Link quantum/time-signature surface, and use `phase` or
`rampbeat` for cycle-relative animation.

Be careful with tempo writeback. If the exposed parameter surface writes Link
tempo, it can affect every peer in the Link session, including Ableton. Do not
bind tempo as a casual macro override.

## MIDI Input Path

TouchDesigner MIDI operators usually depend on the MIDI Device Mapper. Before
building a live MIDI network:

1. Open Dialogs > MIDI Device Mapper.
2. Add the input or output device.
3. Use the mapped device/table and row id expected by the operator.

Choose the operator by the data model:

| Need | Operator |
| --- | --- |
| Continuous CHOP controls from notes/CCs | `midiinCHOP` |
| Portable mapped controls such as `s1` and `b1` | `midiinmapCHOP` |
| Ordered event table for clock, MTC, sysex, or sequencing | `midiinDAT` |

`midiinCHOP` is sampled, so low sample rates can miss fast note-on/note-off
pairs or dense controller motion. Use a sufficiently high rate for performance
control, or switch to `midiinDAT` for exact event order.

14-bit MIDI controller values require paired MSB and LSB controller messages.
Do not enable 14-bit handling unless the controller is known to send those
pairs.

MIDI values can persist in a saved `.toe`. A project saved with a virtual value
that differs from the physical controller can jump on first touch after reload.
Smooth through `lagCHOP` or reset controller state on project open when this
matters.

## MIDI Output Path

Use `midioutCHOP` for channel-driven MIDI output. Input channels must match the
operator's MIDI naming conventions for notes, controls, program changes, clock,
transport, or MTC.

Enable Cook Every Frame for production output that must keep sending clock,
held controls, or realtime state. Without it, output can depend on input
changes or downstream cooking.

For scripted MIDI output, use the MIDI Out CHOP Python API:

```python
out = op("midiout1")
out.sendControl(channel, index, value)
out.sendNoteOn(channel, index, value)
out.sendNoteOff(channel, index, value)
out.sendPitchBend(channel, value)
out.sendProgram(channel, value)
out.sendExclusive(*messages)
out.send(*messages)
out.panic()
```

There is no `midioutDAT`. MIDI Event DAT is for monitoring or receiving MIDI
traffic, not sending it.

## Cross-Plugin Handoff

When LivePilot and TDPilot are both connected, split the work:

- LivePilot configures Ableton Link, tempo, transport, clips, scenes, and
  automation.
- TDPilot creates `abletonlinkCHOP`, enables the required output channels, and
  binds Link channels to TouchDesigner visuals.

Neither plugin automatically calls the other. The agent coordinates the handoff.
If only TDPilot is available, ask the user to enable Link in Ableton manually.

## Macro Starting Points

`ableton_link_sync` creates:

```text
abletonlinkCHOP -> selectCHOP -> mathCHOP -> nullCHOP
```

It enables `tempo`, `beats`, `phase`, and `rampbeat` output channels and exposes
only a `quantum`/signature override. It deliberately does not expose tempo as a
macro override.

`midi_control_mapping` creates:

```text
midiinmapCHOP -> selectCHOP -> mathCHOP -> nullCHOP
```

It selects mapped slider channels and normalizes 0..127 MIDI values into 0..1.
