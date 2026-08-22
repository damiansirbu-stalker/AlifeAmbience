# AlifeAmbience - architecture and method

AlifeAmbience is the most complete and most refined ambient nature-and-weather soundscape for
S.T.A.L.K.E.R. Anomaly and G.A.M.M.A. It selects the best source for each part of the soundscape across
several community packs, deduplicates by waveform, and then engineers every file to sound in the world:
folded to mono so the engine can position it in 3D, distance-corrected so it carries and decays across its
area, and loudness-leveled into an ear-calibrated band. The level and weather config are reconciled into
one closed routing, so every map in every weather state plays an audible living bed.

It is the counterpart to AlifeSpooks. AlifeSpooks owns the horror one-shots and statically vetoes them out
of the base ambient channels; AlifeAmbience owns the continuous nature/weather bed AlifeSpooks leaves
alone. The two never overlap: dread one-shots are AlifeSpooks, the living bed is AlifeAmbience.

This document is the method and the invariants. The build tool is `tools/merge.py`, and every claim about
coverage is proved by a verifier that emits a config-closure ledger, not asserted by hand. The audibility
method is grounded in the X-Ray engine source and the library note
`doc/library/anomaly/internals/sound-source-and-emitter.md`, cited throughout.

## The roster: best-of-breed, not a union

No single pack is the superset, and no pack is audible out of the box. An earlier build merged the whole
union of several packs; measured and ear-tested, that was worse: crammed, muddy, and no cleaner than the
loudest single pack. So the roster is best-of-breed per category, chosen by measurement (`ffmpeg
ebur128`/`astats`, a waveform census, and the engine gain model), not by taste:

- Amplified (Dark Signal Amplified Soundscape) is the config spine, the only pack with a complete
  level/weather config (33 levels, all Atmospherics states, plus GAMMA's extended maps), and the birds
  source. Its own wind and foliage are muffled and stereo, so they are culled.
- Soundscape Overhaul is the environment core: wind, weather, birds, foliage. Its content measured best,
  mostly mono, present, with little too quiet to save.
- Audio Expansion supplies insects and frogs: distinct, loud, mono content no other pack has.
- Immersive Ambience supplies wind reinforcement and the helicopter, loud and mono.
- RETUNE and myRETUNE (Antares) are dropped. Measured, Antares is RETUNE plus loudness (90% byte-identical
  audio, same `base_volume`), 48% stereo, with no unique content; its apparent quality was volume, not craft.

The roster packs share deploy paths (they all write under `soundscape/`), so best-of-breed cannot be a
folder pick: the same path holds either pack's file. Instead it emerges from the audibility pass. The
`level` stage lifts the salvageable content and the `cull` stage drops the dead, per file, wherever it came
from, so the good survives and the muffled dies without hand-selecting folders.

## The audibility method: lossless levers, one ear calibration

A community ambient corpus sounds fine at-ear yet is near-inaudible in-game at range, for engine reasons,
not loudness (`sound-source-and-emitter.md`):

1. A STEREO ogg force-plays 2D at-ear, escaping both distance rolloffs and occlusion; only MONO
   spatialises. Measured: about half the raw corpus is stereo, so half the bed plays in-head.
2. Every 3D voice is attenuated TWICE, X-Ray's linear fade AND OpenAL's inverse model keyed on the ogg
   blob's `min_distance`. A `min_distance` of 1-2 (the unset ffmpeg-era default, most of the raw corpus)
   costs -26..-31 dB at a 25-50 m placement before the linear fade even applies.
3. Content loudness is a separate floor the distance fixes cannot reach: a genuinely quiet recording plays
   inaudibly even at full gain.

The fix is a set of lossless edits to each ogg's own X-Ray comment blob (audio pages byte-identical), keyed
to an in-ear calibration ladder that fixed the target levels:

- Fold to mono (`fold`). The one lossy step, unavoidable since only mono positions: sum L+R, or drop a
  channel for an anti-phase pair. The author blob is captured first; off-rate files are resampled to 44100
  here.
- Crest-inverted min-distance floor (`level`). Floor each file's `min_distance` to a ratio of its channel's
  felt-far placement, the ratio keyed to the sound's crest: a sustained low-crest tone gets a higher ratio
  (0.60) and carries across its band; a sharp high-crest transient gets a lower ratio (0.40) and stays a
  near-field detail. Capped below `max_distance` so a real fade band survives; never lowers an authored
  min. This fixes the OpenAL rolloff.
- Loudness band (`level`). Level `base_volume` into a per-category band, both arms lossless and partial: a
  floor lifts a file whose delivered loudness at its placement is below the audible target, a ceiling lowers
  a file above it. The targets (-30 effective for continuous beds, -36 for one-shots, with -24/-28
  ceilings) are the ear-calibration values, converted through the engine's effects master. Delivered
  loudness is computed from the content LUFS plus the two-rolloff gain, so the band operates on what the
  player actually hears, not the raw file. A file is only ever in one arm, so floor and ceiling never fight.

Placement is the strongest lever and is set in config: a per-category spawn-distance cap keeps a category's
channels from placing too far (wind is capped so it does not sit out past ~65 m). The `cull` stage removes
silent/dead files (measured content below -60 LUFS) and strips their channel refs without ever emptying a
channel. The `audit` stage is the acceptance gate over the wired files, reporting `min/felt-far` and the
crushed share (< 0.15 = whisper) against the crest-floor's own ratio band (0.40-0.60).

The floor, ceiling, cap, and ratios are calibrated constants at the top of their stage in `merge.py`, tuned
by ear; a category wanting a different feel is a constant change, not a different mechanism.

## Deduplication: waveform identity, source side only

Identity is the waveform, never the filename. md5 over the file dedups byte-identical reships among the
source packs; a separate audio-page hash keys the loudness/crest measurement cache, so a rebuild
re-measures only new audio and the cache survives the blob rewrites (which change the comment page, not the
audio pages). Dedup runs among the source packs only, never against the target install.

## The five-link binding chain

A bed sound reaches the player through five hand-authored links. The build owns all five and the verifier
proves each resolves.

1. Weather state. The weather mod's `weathers/w_*.ltx` sets, per time frame, `ambient = <state>`
   (day, morning, evening, night, rain, rain_day, rain_night, storm_day, storm_night, tuman,
   tuman_night, indoor_underground for Atmospherics). This is the join key to the sound layer.
2. Level -> preset. `ambients/<level>.ltx` is a one-line `#include "presets\environment_<name>.ltx"`
   binding each map to a preset. GAMMA's extended levels (bunker_a1, collaider, grimwood, poselok_ug,
   zaton, jupiter) only exist in the Amplified spine, the reason it owns the config.
3. Preset -> channels, per state. `presets/environment_<name>.ltx` has one section per weather state,
   each with `sound_channels` (the continuous bed) and `sound_channels_dynamic` (the layered one-shots:
   wind, birds, bugs, crows, foliage, frogs, ...).
4. Channel -> folder. `ambient_channels/backgrounds.ltx` and `sound_channels.ltx` map each channel name
   to a sound-folder path.
5. Folder -> ogg. The engineered audio files.

X-Ray lowercases section names on load (`strlwr(section)`, `Xr_ini.cpp:1613`), so channel and state
references resolve case-insensitively.

## Config closure - the proof that everything is wired

The build is not a file dump. Grafting content (e.g. Audio Expansion's frogs) means authoring a channel in
`backgrounds.ltx`/`sound_channels.ltx`, referencing it in the right preset sections, binding those presets
to the right levels, and covering every weather state. A verifier proves the whole config is closed before
any build is released, emitting a ledger with six invariants. The build fails unless every one is clean:

1. No orphan file - every deployed bed ogg sits under a folder some channel points at.
2. No orphan channel - every defined channel is referenced by some preset (informational: unused
   definitions are harmless, they never load).
3. No dangling channel ref - every channel named in a preset is defined.
4. No missing sound path - every channel's path resolves to audio on disk.
5. Level routing closed - every level binds a preset (underground levels -> underground presets,
   surface -> outdoor), and every active map resolves.
6. Weather matrix full - every preset defines a section for every state the active weather mod emits;
   the (map x weather-state) matrix has no empty cell.

The weather matrix (invariant 6) is the single coupling to the weather mod. For Atmospherics it is the 12
states above; a weather-mod swap re-greps the new `ambient=` vocabulary and the same matrix must stay full.
Everything below link 1 (levels, channels, folders, oggs) is weather-mod-independent.

Stock-pack defects the build fixes (found by an early closure audit of the Amplified spine): dangling
channel refs such as `wind_trong` (a typo of `wind_strong`) that play silent in the stock pack. The
verifier drives invariant 3 to zero.

## Coexistence with AlifeSpooks

AlifeSpooks captures the dark/horror content from the same source packs and vetoes it out of the base
ambient channels at config load. AlifeAmbience owns the non-dark bed. Because AlifeSpooks's veto removes
only its own captured sounds at the source paths, and AlifeAmbience provides the nature/weather bed those
packs leave for the base, the two compose without doubling: horror is placed by the AlifeSpooks director,
the living bed is the AlifeAmbience config. Run both.

## Content pipeline (reproducible)

`tools/merge.py` is a pipeline; each stage reads the previous stage's output on disk. `python merge.py
rebuild` wipes and regenerates the whole corpus; each stage is also runnable alone. `fold` is the long one
(per-file ffmpeg). `add` reruns without wiping, but `graft` appends, so `rebuild` is the path after any
config or roster change.

```
plan     hash the roster packs' oggs, dedup by path                     -> manifest.json
deploy   copy the chosen files + the Amplified config subset (spine)     -> gamedata/
config   fix stock defects, strip dead refs, cap spawn distance per cat  -> gamedata/ (config)
graft    wire best-of-breed folders into channels + presets; frogs/heli  -> gamedata/ (config)
prune    delete every file no channel references                        -> gamedata/sounds
fold     stereo -> mono (re-encode) + resample off-rate to 44100        -> gamedata/sounds, fold_blobs.json
master   RETIRED no-op (min floor moved into level, crest-inverted)     -> -
level    crest-inverted min floor + loudness band, one crest+LUFS pass  -> gamedata/sounds, level_cache.json
cull     delete silent/dead files, strip refs (never empty a channel)   -> gamedata/sounds
verify   config-closure ledger (6 invariants)                           -> ledger.tsv
audit    wired min/felt-far ratio + crushed share (acceptance gate)     -> stdout
```

The min-distance floor and the loudness band are consolidated into `level` so both key off one crest+LUFS
measurement (matching AlifeSpooks' `_normalize_blobs`); `master` is a retired no-op kept for stage
compatibility. The LUFS/crest measurement is cached by audio-page hash, so a rerun re-measures only new
audio. `cull` runs after `level` (it needs the measurement) and re-prunes so no ref is left dangling.

Sources are the registry `tools/sources.py`: one entry per pack (name, path, url, licence, role). A licence
gate stops the build on any source not cleared. Sources are always pulled locally by hand; the pipeline
never downloads, so `url` is a credit/provenance reference only.

## Invariants

- I1 Bed only. AlifeAmbience owns the continuous nature/weather bed. Horror one-shots are AlifeSpooks;
  emission and psi-storm are their own systems and are never touched.
- I2 Audible and leveled, by measurement. Three levers make a file sound: mono fold (only mono positions),
  a crest-inverted `min_distance` floor (the OpenAL rolloff anchor), and a `base_volume` loudness band
  (floor lifts quiet, ceiling eases hot) to an ear-calibrated target computed from delivered loudness. The
  game's ambient volume slider sets the overall level on top.
- I3 Preserve the source, except where the engine forbids it. `level` rewrites only the ogg comment blob
  (min/max/base_volume), losslessly; audio pages byte-identical. The one exception is `fold`: a stereo file
  MUST be re-encoded to mono (a lossy pass) because the engine only positions mono; its author blob is
  captured first so `level` can restore and then floor min/max/base_volume.
- I4 Deduplicate by waveform, source side only. Never against the target install.
- I5 Config is closed. The six-invariant ledger passes, or the build fails. No silent map, no silent
  weather, no dangling ref.
- I6 Weather-mod-bound at exactly one link. The preset state set covers the active weather mod's emitted
  states; nothing else depends on the weather mod.
- I7 Reproducible. `plan -> deploy -> config -> graft -> prune -> fold -> master -> level -> cull -> verify
  -> audit` (`merge.py rebuild`) regenerates the whole bed and its proofs from the packs.
- I8 Traceable. Every deployed sound resolves to its origin via `manifest.json`; every source is credited in
  the readme and cleared in `licensing.md`.

## Scripts: dependency gate, MCM, diagnostics (no gameplay)

AlifeAmbience provides audio and config; its Lua is a thin diagnostic and compatibility layer only, a mirror
of the family shape so its tooling reads identically to the other mods. No gameplay logic runs.

- `_aa_deps.script` - the version constant (`get_version`), the xlibs + modded-exes floor asserts, the
  `platform_status`/`platform_functor` line, and the boot banner to `alifeambience.log`. Because it has
  scripts, the compatibility floor (xlibs + demonized/AOE) applies to AlifeAmbience on load, uniform with
  the family (`compatibility-standards.md`).
- `aa_mcm.script` - the MCM menu, informational: a General tab with the platform/version footer, and a
  Development tab (log level, the "log ambient wiring on load" toggle, reset). There is NO master volume
  slider. Loudness is leveled at build time into the blob (I2) and the game's own ambient volume slider
  sets the overall level; a per-mod slider would need a runtime ambient hook this config-only bed does not
  have.
- `aa_debug.script` - one xlog logger plus the `aa_debug.on()/dbg()/info()/warn()` gate, level from MCM.
- `aa_diag.script` - the runtime wiring inspector. On load (and on demand via `aa_diag.dump()` from the
  console) it logs the active level, weather, and ambient state; the per-state dynamic channel counts of
  the current preset (the density picture that explains why one install fires more often than another); the
  active bed channel and whether it resolves; and a live dangling-ref count. Gated on DEBUG or the
  Development toggle.

## Deploy

A gamedata overlay. The repo holds the buildable source, the tool, the docs, and the audio. Wired for local
sync and the gamma-redux install through `stalker-manager` (AlifeAmbience is a local external there, so
`apply-gamma-redux` copies its gamedata and enables it). Every source is freely licensed or used with the
author's permission, granted for my mods, not per mod (see `licensing.md`); each is credited, and none is
included without a license or the author's consent.
