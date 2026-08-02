# AlifeAmbience - architecture

A dark-mood ambient overlay for S.T.A.L.K.E.R. Anomaly / G.A.M.M.A. It gathers
the dark, dreadful, and mournful sounds from several soundscape packs, keeps the
best-quality copy of each, and composes them on top of whatever ambient setup is
installed, using DLTX. It does not replace the ambient system; it layers onto it.
The scope is immersion and variety, not raw content or volume.

This document is the method and the invariants. The build tool is `tools/merge.py`.

## How the ambient system works (the ground truth)

The Anomaly soundscape is two independent players reading the same config, and
they must not be confused (full mechanics with `file:line` in the stalker-dev
library note "ambient-sound-system"):

- Engine static bed - C++ `CGamePersistent::WeathersUpdate`, reads the `sound_channels` key, plays the single background bed per place. Distance is its only volume lever.
- Lua dynamic layers - `sound_ambient.script`, reads the `sound_channels_dynamic` key, plays the rotating dread/atmosphere layers. This is the layer AlifeAmbience targets.

Facts that govern every design choice below:

- A place is one (level preset, time-of-day) section. Its `sound_channels_dynamic` is a list of channel names. That list length is the number of PARALLEL CHANNELS at that place.
- Each channel is a named set: a `sounds` list plus one `min_distance`, `max_distance`, `period0..3`, and optional `height` / `indoor`.
- The script round-robins one channel per second. On a channel's turn it plays ONE sound chosen uniform-random with replacement (not a queue, not sequential), at a random distance in the channel's band, then reschedules itself by one of its four periods chosen at random.
- Two frequency levers, not one. Channel count per place sets how many textures cycle and how long the cycle is; a channel's periods relative to that cycle set how often it actually fires. When periods are shorter than the cycle, every channel fires once per cycle and the aggregate rate is about one sound per second regardless of channel count. Genuinely calmer than vanilla requires periods LONGER than the cycle.
- Loudness has no per-channel key. The levers are distance (farther is quieter), the `indoor` flag (an outdoor cue flagged indoor plays at zero outdoors), and the global MCM `ambient_volume`.
- Files inside a channel are variety only. Adding sounds to a channel lowers repetition and costs disk; it has zero effect on frequency or density.

## Why an overlay, not an override

DLTX composes onto `environment/sound_channels.ltx` and the ambient presets: it
adds sections, revives muted ones, and appends to or removes from the sound and
channel lists, without replacing the base file (engine loads these via CInifile,
which is DLTX-aware). Operators: `@[sec]` add, `![sec]` override/extend,
`>key = item` append to a list, `<key = item` remove from a list. So
AlifeAmbience:

- Layers on top of any ambient setup (GAMMA, vanilla, another soundscape) instead of overriding it.
- Ships only its own dark content, not a full copy of the ambient system.
- Cannot cause a missing-channel CTD, because the base stays intact and the engine's strict channel asserts only run on the static bed, never on our appended dynamic layers.
- Stays portable and modest in size.

## Invariants

- I1 Compose, never override. Ship DLTX patches, not full copies of the ambient config.
- I2 Curation from each pack's channel assignments, not folder-name guessing. A sound belongs to a channel because a pack author put it there.
- I3 Dedup by exact content hash (md5), pooled per merged family. Byte-identical reships collapse; distinct sounds never merge. Acoustic fingerprinting is not used (it merged 25 distinct screams to 4).
- I4 Fitness is codec + sample rate: 44100 Hz vorbis. Off-spec files are dropped.
- I5 Baseline in LTX, feel at runtime. The LTX carries a sane per-channel baseline (the pack values, lightly normalized), so what plays is reasonable even with the control layer neutral. Loudness, distance, and rarity are enforced by the runtime control layer as global policies with an absolute floor (calmer than vanilla by construction), live-adjustable from MCM. Exact per-channel feel is not hand-computed into the LTX.
- I6 Density is enforced at runtime by an audible-count ceiling, not a static list truncation. The ceiling is informed by vanilla's own figures (about 10 average, 13 max parallel channels). The build still surveys and reports per-place channel counts as a sanity check, but overload is prevented live; this is what lets the content stay generous without muddiness.
- I7 Family-merge is a content tool, not a density mechanism. It pools same-role source channels into one merged channel (deduped union of their sounds) for variety and cross-variant dedup. Merge only within an equivalence class (same distance band, cadence, `indoor`/`height`, semantic family).
- I8 Variety is free. A channel may hold as many sounds as pass I3 and I4; sound count is never capped for density reasons, only by quality and dedup.
- I9 Dark scope only. Keep dark/horror/dreadful/sad channels; drop generic daytime life (birds, insects, plain wind, pleasant beds), which the base ambience already provides.
- I10 Leave emission alone. Blowout and psi-storm are their own system.
- I11 Reproducible. plan -> presets -> deploy regenerates from the source packs; a pack change is a re-run.
- I12 Credit every source (author + link) in the readme.
- I13 The mod ships a runtime control layer: one script family that owns the single dynamic-layer play function `sound_ambient.update_ambient` and, on each play, applies the loudness, density, and rarity policies the LTX cannot express, plus the announce diagnostic as its read-only facet. Built on xlibs (xlog, xmcm, xprofiler), mirroring the alife-family pattern. No config override, exactly one vanilla function replaced.
- I14 Neutral is pass-through. The control layer reimplements `update_ambient` faithfully; with every control at its neutral value it behaves identically to vanilla, so it never breaks base ambience. Each control is MCM-exposed and defaults to a value consistent with the invariants above (calm, capped, quiet).

## Density invariant (the numbers)

Parallel channels per place, surveyed across every source that ships ambient
presets:

| Source | Places | Avg | Median | p90 | Max |
|--------|--------|-----|--------|-----|-----|
| vanilla Anomaly | 72 | 9.7 | 9 | 12 | 13 |
| Soundscape Overhaul | 240 | 5.6 | 5 | 8 | 11 |
| Dark Signal Weather | 240 | 5.6 | 5 | 8 | 11 |
| RETUNE | 241 | 6.6 | 6 | 11 | 13 |
| DarkSignal Amplified | 349 | 5.7 | 5 | 8 | 11 |

Vanilla is the densest on average and its maximum is 13; no pack exceeds it. These
figures (about 10 average, 13 max) inform the runtime audible-count ceiling (I6),
not a static list truncation. The prior full-override build peaked at 26 parallel
channels per place; that overload is the failure the runtime concurrency cap
prevents, while letting the content stay generous.

## Settings: baseline in LTX, feel at runtime

The LTX carries a sane per-channel baseline so what plays is reasonable even with
the control layer neutral:

- min_distance / max_distance / periodN: the pack values, lightly normalized (a single definer used as-is; muted definers ignored; period order kept valid, p1>=p0 and p3>=p2).
- height / indoor: carried from the definer; an outdoor dread channel is never flagged indoor.

Feel is enforced at runtime by the control layer, not hand-computed into the LTX:

- Loudness: a global and per-family volume factor on `ch.snd.volume` (no LTX equivalent exists).
- Rarity: a period floor and multiplier at play time, so a channel is genuinely rarer than the round-robin cycle, which the LTX alone cannot guarantee (the cycle floors every channel at one check per its length).
- Distance: a global factor on the computed spawn radius.

All are MCM-exposed and pass-through at their neutral value (I14).

## Channel-family merge

A merged channel folds several same-role source channels into one named channel
whose `sounds` list is the deduped union of the members. In presets, the member
names are replaced by the single merged name. This lowers the parallel-channel
count while keeping every sound (variety preserved), and the pooled dedup catches
cross-variant reships. The merge map is committed data, applied in `plan`. The
same-role constraint (I7) is enforced: only channels in one distance/cadence/
indoor/family class merge together.

## Runtime control layer

Owning `sound_ambient.update_ambient` is a control point, not only a probe: every
value the function computes per play (sound, distance, volume, schedule) is ours
to modify before the sound goes out. This is what lets the mod enforce, at
runtime, the "feel" the static LTX cannot express. Controls, highest value first:

- Loudness - the LTX has no per-channel volume key; the script sets `ch.snd.volume`. The layer scales it per family or globally, the only runtime loudness lever, and the answer to "not too loud".
- Live concurrency - the static ceiling caps channel count, not how many sounds are audible at once (rate x duration). The layer tracks live handles and skips a play when the audible count is at a ceiling; the guarantee against overload that no static config can give.
- Rarity - scale the reschedule period at runtime (an MCM "dread frequency" knob).
- Distance - scale the computed spawn distance at runtime.
- Context-gated dread (staged) - bias or gate dark layers by time-of-day, danger, health, or level. The largest scope; added last.

Scope is global. Because the layer owns the one function every dynamic ambient
sound passes through, its policies apply to the whole soundscape - GAMMA's
channels, another soundscape's, and ours alike - so the entire Zone conforms to
one dark, calm, capped ambience, not just our added layers.

Global reach does not cost per-channel precision. Every play hands the layer the
firing channel's name, so policies are keyed per channel or per family - the same
classification applied to GAMMA's channels and ours alike - with a global default
for any channel we have no specific rule for. A scream family can be quieter and
rarer than a wind family, across the whole soundscape.

Division of responsibility: the DLTX config owns content (which channels and
sounds exist, and which play at each place) and a sane baseline; the runtime layer
owns feel (loudness, live concurrency, rarity, distance). The config cannot
express feel; the layer cannot invent content. Neither replaces the other.

Every control is a pass-through at its neutral value (I14). The engine static bed
is C++ and not Lua-controllable; extending control to it needs a demonized-exe
volume/veto hook plus the xlibs fallback (future), the same dual path as the
announce.

## Ambient announce (diagnostic, MCM)

The read-only facet of the control layer: an MCM-gated diagnostic that makes every
ambient sound visible for verification and curiosity, so density and settings are
checked by observation, not guessed by ear. Default off; when off it is inert.

- MCM page "AlifeAmbience": "Announce ambient sounds on screen" (a PDA tip) and "Log ambient sounds to file", independent toggles, both default off.
- On each play it reports channel name, file, distance, and volume, plus the underground/inside context.
- Two systems, two paths:
  - Lua dynamic layers (`sound_channels_dynamic`) - traced now, by monkey-patching `sound_ambient.update_ambient` with a behavior-identical instrumented copy while a toggle is on.
  - Engine static bed (`sound_channels`) - played in C++ (`GamePersistent::WeathersUpdate`), not reachable from Lua. A demonized-exe PR fires a script callback at the bed play site; the mod registers a handler through the xlibs fallback pattern, so it is a silent no-op on unpatched exes and starts tracing the bed once the PR is merged. This is the same PR-plus-xlibs-fallback pattern the other alife-family mods use.
- Requires xlibs (the fallback plumbing), consistent with the other alife-family mods.

## Pipeline (tools/merge.py)

- plan - parse every source pack's `sound_channels.ltx`. Pool each channel's sounds, resolve to files, dedup by content hash, drop off-spec and junk-bitrate. Apply the dark scope (I9) and the family-merge map (I7). Compute each channel's settings by I5. Fill a channel whose curated content does not resolve from a declared source. Output: `merged_channels.json`.
- presets - parse every pack's presets. For each place, union the dark layers, filter to channels we ship, and survey the per-place channel count (reported for sanity; overload is prevented at runtime, I6). Output: `merged_presets.json`.
- deploy - emit a DLTX overlay: `mod_sound_channels_alifeambience.ltx` (add dark channels with `@[...]`, revive/enrich with `![...]` + `>sounds`), `mod_<preset>_alifeambience.ltx` files that append the dark layers per place, and copy the dark sound files into `sounds/`. No full `sound_channels.ltx`, no preset replacement.
- validate (soundpool.py) - every referenced sound resolves; no dangling; report the per-place channel-count distribution and flag any place at or over the ceiling.

## Tools and process

- `pools.json` - source registry (name, gamedata root, author, url, quality gates). Adopting a pack: add it here.
- committed classification data - the dark keep/drop lists (I9) and the channel-family merge map (I7), read by `plan`.
- `merge.py` - the pipeline above.
- `soundpool.py` - probe (ffprobe), dedup helpers, and the validate + density survey.

Adopting new sounds or channels is a fixed process: refresh the pack on disk, add
it to `pools.json`, classify any new channel (dark or not, and its family), re-run
plan -> presets -> deploy, and read the validate + density survey. Nothing is added by
hand; every deployed sound traces to a source pack and a channel assignment.

## Dark scope

Kept: dread cues (spooks, screams, mutant growls, dark ambience, dark_signal),
all underground, tension (distant gunfire, ominous drones, creeping wind, branch
creaks), eerie atmosphere (owls, distant dogs, crows, fog), and oppressive weather
(storms, rain, howling wind). Dropped: daytime birdsong, insects, plain wind,
pleasant tree and foliage rustle, and the neutral base beds. Emission is left to
its own system.

## Deploy

Wired in `stalker-manager/gamma-redux.yaml` as a `path` external. As a DLTX overlay
it can sit anywhere in load order and still compose. Distributed as a GitHub
Release zip and/or moddb; the repo holds the buildable source (tool + docs), with
the sound files either committed (if trimmed under the GitHub size guidance) or
attached to a release.

## Source and status

Built from four packs (Dark Signal Weather, Dark Signal Amplified, Soundscape
Overhaul, RETUNE) plus vanilla for channel coverage. The prior full-override build
(Zone Soundscape) is kept as a reference; this repo is the overlay rebuild.
Credits and per-source detail in `readme.txt`.
