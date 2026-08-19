# AlifeAmbience - architecture and method

AlifeAmbience is the audible nature-and-weather ambient bed for S.T.A.L.K.E.R. Anomaly and G.A.M.M.A.
It merges the best ambient beds from several community soundscape packs into one curated set, re-levels
every file to one even loudness, and reconciles the level and weather config into a single closed
routing, so every map in every weather state plays an audible living bed.

It is the counterpart to AlifeSpooks. AlifeSpooks owns the horror one-shots and statically vetoes them
out of the base ambient channels; AlifeAmbience owns the continuous nature/weather bed AlifeSpooks
leaves alone (its scope rule I9: "leave generic daytime life and the base weather bed to the base
ambience"). The two never overlap: dread one-shots are AlifeSpooks, the living bed is AlifeAmbience.

This document is the method and the invariants. The build tool is `tools/merge.py`, and every claim
about coverage is proved by a verifier that emits a config-closure ledger, not asserted by hand.

## Why a merge, not a pick

No shipped pack is the superset. Measured across the candidate beds (`ffmpeg ebur128`, folder census):

- The `soundscape/` framework (Solarint's) is byte-identical across RETUNE, myRETUNE Antares, Dark
  Signal 304, and Soundscape Overhaul - it is not a differentiator.
- Dark Signal Amplified has the widest content (foliage, dense insects/wind, rain, crows, debris) and
  the widest config (33 levels, all Atmospherics weather states), but its background bed loops are dead
  (-45 to -70 LUFS - the "dead calm-day air").
- RETUNE / myRETUNE Antares have the only audible background bed loops (-15 to -49 LUFS) but a thin
  content set.
- Audio Expansion has the richest species tree (frogs, time-of-day insects, night birds, bats) but
  ships zero config.

So the merge takes: Amplified as the content and config spine, RETUNE/Antares as the audible bed
masters, Audio Expansion for species, Immersive Ambience for weather events, Dark Signal Unused
Interior for interiors - deduplicated and re-leveled to one target. The result is a living day/night
ecosystem, audible, that no single pack is.

## The five-link binding chain

A bed sound reaches the player through five hand-authored links. The merge owns all five and the
verifier proves each resolves.

1. Weather state. The weather mod's `weathers/w_*.ltx` sets, per time frame, `ambient = <state>`
   (day, morning, evening, night, rain, rain_day, rain_night, storm_day, storm_night, tuman,
   tuman_night, indoor_underground for Atmospherics). This is the join key to the sound layer.
2. Level -> preset. `ambients/<level>.ltx` is a one-line `#include "presets\environment_<name>.ltx"`
   binding each map to a preset. GAMMA's extended levels (bunker_a1, collaider, grimwood, poselok_ug,
   zaton, jupiter) only exist in the Amplified spine - the reason it owns the config.
3. Preset -> channels, per state. `presets/environment_<name>.ltx` has one section per weather state,
   each with `sound_channels` (the continuous bed) and `sound_channels_dynamic` (the one-shot layer:
   wind, birds, bugs, crows, foliage, frogs, ...).
4. Channel -> folder. `ambient_channels/backgrounds.ltx` and `sound_channels.ltx` map each channel name
   to a sound-folder path.
5. Folder -> ogg. The leveled audio files.

X-Ray lowercases section names on load (`strlwr(section)`, `Xr_ini.cpp:1613`), so channel and state
references resolve case-insensitively.

## Masterization: level to one target, losslessly

Every kept bed is re-leveled so its average loudness (astats Overall RMS) lands on one target, by
overwriting only the `base_volume` value in the ogg comment blob - a lossless header rewrite, the audio
pages untouched. Peak-capped so nothing clips, floored so nothing falls under the engine cull. This is
the same masterization AlifeSpooks uses (`_level_base_volume` / `_normalize_blobs` / `_write_blob`),
extracted into a shared, target-parameterized module: AlifeSpooks levels its dark corpus to the corpus
median; AlifeAmbience levels its bed to an explicit LUFS target so the "dead calm-day air" is gone and
the whole bed sits at one even, audible level. Attenuation (min/max distance) stays each source's own.

## Deduplication: waveform identity, source side only

Identity is the waveform, never the filename or bytes. md5 for byte-identical reships; Chromaprint
fingerprint to propose re-encoded copies; PCM cross-correlation to decide, under complete linkage so a
similarity chain never collapses two distinct recordings. Runs among the source packs only.

## Config closure - the proof that everything is wired

The merge is not a file dump. Grafting content (e.g. Audio Expansion's frogs) means authoring a channel
in `backgrounds.ltx`/`sound_channels.ltx`, referencing it in the right preset sections, binding those
presets to the right levels, and covering every weather state. A verifier proves the whole config is
closed before any build ships, emitting a ledger with six invariants. The build fails unless every one
is clean:

1. No orphan file - every shipped bed ogg sits under a folder some channel points at.
2. No orphan channel - every defined channel is referenced by some preset.
3. No dangling channel ref - every channel named in a preset is defined.
4. No missing sound path - every channel's path resolves to audio on disk.
5. Level routing closed - every level binds a preset (underground levels -> underground presets,
   surface -> outdoor), and every active map resolves.
6. Weather matrix full - every preset defines a section for every state the active weather mod emits;
   the (map x weather-state) matrix has no empty cell.

The weather matrix (invariant 6) is the single coupling to the weather mod. For Atmospherics it is the
12 states above; a weather-mod swap re-greps the new `ambient=` vocabulary and the same matrix must stay
full. Everything below link 1 (levels, channels, folders, oggs) is weather-mod-independent.

Stock-pack defects the merge fixes (found by an early closure audit of the Amplified spine): four
dangling channel refs - `wind_trong` (typo of `wind_strong`), `branch_spook`, `bugs`, `drones_day` -
that play silent in the stock pack. The verifier drives invariant 3 to zero.

## Coexistence with AlifeSpooks

AlifeSpooks captures the dark/horror content from the same source packs and vetoes it out of the base
ambient channels at config load. AlifeAmbience owns the non-dark bed. Because AlifeSpooks's veto removes
only its own captured sounds at the source paths, and AlifeAmbience ships the nature/weather bed those
packs leave for the base, the two compose without doubling: horror is placed by the AlifeSpooks
director, the living bed is the AlifeAmbience config. Run both.

## Content pipeline (reproducible)

`tools/merge.py` is a pipeline; each stage reads the previous stage's committed artifact.

```
plan        source bed trees, deduped by waveform     -> merged_beds.json
classify    measured features per sound               -> classification.json
loudness    per-file loudness, target computed        -> loudness_outliers.json
deploy      leveled audio + reconciled config         -> gamedata/
verify      config-closure ledger (6 invariants)      -> ledger.tsv
provenance  every shipped sound -> its origin          -> provenance.tsv
```

Sources are the registry `tools/sources.py`: one entry per pack (name, path, url, licence). A licence
gate stops the build on any source not cleared. Sources are always pulled locally by hand; the pipeline
never downloads, so `url` is a credit/provenance reference only.

## Invariants

- I1 Bed only. AlifeAmbience owns the continuous nature/weather bed. Horror one-shots are AlifeSpooks;
  emission and psi-storm are their own systems and are never touched.
- I2 Level, do not overpower. Every bed is leveled to one target loudness; the mix sits within the base
  range, one master MCM slider balances against a base if one runs unusually loud or quiet.
- I3 Ship byte for byte. Audio pages are the source's own, untouched; only the X-Ray comment blob is
  rewritten losslessly (base_volume leveled, min/max the source's).
- I4 Deduplicate by waveform, source side only. Never against the target install.
- I5 Config is closed. The six-invariant ledger passes, or the build fails. No silent map, no silent
  weather, no dangling ref.
- I6 Weather-mod-bound at exactly one link. The preset state set covers the active weather mod's
  emitted states; nothing else depends on the weather mod.
- I7 Reproducible. plan -> classify -> loudness -> deploy -> verify -> provenance regenerates the whole
  bed and its proofs from the packs.
- I8 Traceable. Every shipped sound resolves to its origin via `provenance.tsv`; every source is
  credited in the readme and cleared in `licensing.md`.

## Deploy

A gamedata overlay. The repo holds the buildable source, the tool, the docs, and the audio. Wired for
local sync and the gamma-redux install through `stalker-manager`. Distribution of the audio is gated on
per-source licence clearance for this mod (see `licensing.md`); until every bed source is cleared for
AlifeAmbience specifically, the repo is private and the audio is not publicly redistributed.
