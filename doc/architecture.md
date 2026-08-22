# AlifeAmbience - architecture and method

AlifeAmbience is a curated ambient nature-and-weather soundscape for S.T.A.L.K.E.R. Anomaly.
It selects the best source for each part of the soundscape across several community packs, deduplicates by waveform, and then engineers every file to sound in the world:
folded to mono so the engine can position it in 3D, distance-corrected so it carries and decays across its area, and loudness-leveled into an ear-calibrated band.
It reconciles the level and weather config into one closed routing, so every map in every weather state plays an audible living soundscape.

It is the counterpart to AlifeSpooks. AlifeSpooks owns the horror one-shots and statically vetoes them out of the base ambient channels.
AlifeAmbience owns the continuous nature/weather ambience AlifeSpooks leaves alone. The two never overlap: dread one-shots are AlifeSpooks, the living ambience is AlifeAmbience.

This document is the method and the invariants. The build tool is `tools/merge.py`. A verifier that emits a config-closure ledger proves every coverage claim, rather than the doc asserting it by hand.
The audibility method draws on the X-Ray engine source and the library note `doc/library/anomaly/internals/sound-source-and-emitter.md`, cited throughout.

## Source roster

No single pack is the superset, and no pack is audible out of the box. An earlier build merged the whole union of several packs. Measured and ear-tested, that was worse: crammed, muddy,
and no cleaner than the loudest single pack. So the roster is best-of-breed per category, chosen by measurement (`ffmpeg ebur128`/`astats`, a waveform census, and the engine gain model), not by taste:

- Amplified (Dark Signal Amplified Soundscape) is the config spine, the only pack with a complete level/weather config (33 levels, all Atmospherics states, plus the extended maps),
  and the birds source. Its own wind and foliage are muffled and stereo, so the build culls them.
- Soundscape Overhaul is the environment core: wind, weather, birds, foliage. Its content measured best, mostly mono, present, with little too quiet to save.
- Audio Expansion supplies insects and frogs: distinct, loud, mono content no other pack has.
- Immersive Ambience supplies wind reinforcement and the helicopter, loud and mono.
- The build drops RETUNE and myRETUNE (Antares). Measured, Antares is RETUNE plus loudness (90% byte-identical audio, same `base_volume`), 48% stereo, with no unique content.
  Its apparent quality was volume, not craft.

The roster packs share deploy paths (they all write under `soundscape/`), so best-of-breed cannot be a folder pick: the same path holds either pack's file. Instead it emerges from the audibility pass.
The `level` stage lifts the salvageable content and the `cull` stage drops the dead, per file, wherever it came from, so the good survives and the muffled dies without hand-selecting folders.

## Audibility method

A community ambient corpus sounds fine at-ear yet is near-inaudible in-game at range, for engine reasons, not loudness (`sound-source-and-emitter.md`):

1. A STEREO ogg force-plays 2D at-ear, escaping both distance rolloffs and occlusion. Only MONO spatialises. Measured: about half the raw corpus is stereo, so half the ambience plays in-head.
2. Every 3D voice attenuates TWICE, through X-Ray's linear fade AND OpenAL's inverse model keyed on the ogg blob's `min_distance`. A `min_distance` of 1-2 (the unset ffmpeg-era default,
   most of the raw corpus) costs -26..-31 dB at a 25-50 m placement before the linear fade even applies.
3. Content loudness is a separate floor the distance fixes cannot reach: a genuinely quiet recording plays inaudibly even at full gain.

The fix is a set of lossless edits to each ogg's own X-Ray comment blob (audio pages byte-identical), keyed to an in-ear calibration ladder that fixed the target levels:

- Fold to mono (`fold`). The one lossy step, unavoidable since only mono positions: sum L+R, or drop a channel for an anti-phase pair. It captures the author blob first
  and resamples off-rate files to 44100 here.
- Crest-inverted min-distance floor (`level`). Floor each file's `min_distance` to a ratio of its channel's felt-far placement, the ratio keyed to the sound's crest.
  A sustained low-crest tone gets a higher ratio (0.60) and carries across its band. A sharp high-crest transient gets a lower ratio (0.40) and stays a near-field detail.
  The floor caps below `max_distance` so a real fade band survives, and never lowers an authored min. This fixes the OpenAL rolloff.
- Loudness band (`level`). Level `base_volume` into a per-category band, both arms lossless and partial. A floor lifts a file whose delivered loudness at its placement sits below the audible target,
  and a ceiling lowers a file above it. The targets (-30 effective for continuous ambience, -36 for one-shots, with -24/-28 ceilings) come from the ear calibration,
  converted through the engine's effects master. The band computes delivered loudness from the content LUFS plus the two-rolloff gain, so it operates on what the player actually hears,
  not the raw file. A file is only ever in one arm, so floor and ceiling never fight.

Placement is the strongest lever, and config sets it: a per-category spawn-distance cap keeps a category's channels from placing too far (the cap holds wind so it does not sit out past ~65 m).
The `cull` stage removes silent/dead files (measured content below -60 LUFS) and strips their channel refs without ever emptying a channel.
The `audit` stage is the acceptance gate over the wired files, reporting `min/felt-far` and the crushed share (< 0.15 = whisper) against the crest-floor's own ratio band (0.40-0.60).

The floor, ceiling, cap, and ratios live as calibrated constants at the top of their stage in `merge.py`, and ear-tuning sets them. A category wanting a different feel needs a constant change, not a different mechanism.

## Deduplication

Deduplication runs at two levels. `plan` dedups by BYTE hash: an md5 collapses byte-identical reships, keyed by config path.
The same recording at two referenced paths still both ship, because a channel points at each.
`fingerprint` then dedups by ACOUSTIC identity. fpcalc (Chromaprint) fingerprints every deployed file and collapses same-recording aliases the byte hash cannot see:
the same sound re-encoded or renamed to different bytes, about 1.4% of the corpus.
Each group keeps one canonical file, its aliases' config references repoint to it, and the alias files drop.
A channel's pick-pool then never holds the same recording twice under two names.
Fingerprints run on the original audio, before the fold re-encodes it, and cache by audio-page hash.
Short clips fpcalc cannot read fall back to the byte hash. None of this runs against the target install.

## The five-link binding chain

An ambient sound reaches the player through five hand-authored links. The build owns all five, and the verifier proves each resolves.

1. Weather state. The weather mod's `weathers/w_*.ltx` sets, per time frame, `ambient = <state>` (day, morning, evening, night, rain, rain_day, rain_night, storm_day, storm_night, tuman, tuman_night,
   indoor_underground for Atmospherics). This is the join key to the sound layer.
2. Level -> preset. `ambients/<level>.ltx` is a one-line `#include "presets\environment_<name>.ltx"` binding each map to a preset. The extended levels (bunker_a1, collaider, grimwood, poselok_ug,
   zaton, jupiter) only exist in the Amplified spine, the reason it owns the config.
3. Preset -> channels, per state. `presets/environment_<name>.ltx` has one section per weather state,
   each with `sound_channels` (the continuous background layer) and `sound_channels_dynamic` (the layered one-shots such as wind, birds, bugs, crows, foliage, and frogs).
4. Channel -> folder. `ambient_channels/backgrounds.ltx` and `sound_channels.ltx` map each channel name to a sound-folder path.
5. Folder -> ogg. The engineered audio files.

X-Ray lowercases section names on load (`strlwr(section)`, `Xr_ini.cpp:1613`), so channel and state references resolve case-insensitively.

## Config closure

The build is not a file dump. Grafting content (e.g. Audio Expansion's frogs) means authoring a channel in `backgrounds.ltx`/`sound_channels.ltx`, referencing it in the right preset sections,
binding those presets to the right levels, and covering every weather state. A verifier proves the whole config is closed before release, emitting a ledger with six invariants.
The build fails unless every one is clean:

1. No orphan file - every deployed ambient ogg sits under a folder some channel points at.
2. No orphan channel - every defined channel is referenced by some preset (informational: unused definitions are harmless, they never load).
3. No dangling channel ref - every channel named in a preset is defined.
4. No missing sound path - every channel's path resolves to audio on disk.
5. Level routing closed - every level binds a preset (underground levels -> underground presets, surface -> outdoor), and every active map resolves.
6. Weather matrix full - every preset defines a section for every state the active weather mod emits. The (map x weather-state) matrix has no empty cell.

The weather matrix (invariant 6) is the single coupling to the weather mod. For Atmospherics it is the 12 states above.
A weather-mod swap re-greps the new `ambient=` vocabulary, and the same matrix must stay full. Everything below link 1 (levels, channels, folders, oggs) is weather-mod-independent.

Stock-pack defects the build fixes (found by an early closure audit of the Amplified spine): dangling channel refs such as `wind_trong` (a typo of `wind_strong`) that play silent in the stock pack.
The verifier drives invariant 3 to zero.

## Coexistence with AlifeSpooks

AlifeSpooks captures the dark/horror content from the same source packs and vetoes it out of the base ambient channels at config load. AlifeAmbience owns the non-dark ambience.
Because AlifeSpooks's veto removes only its own captured sounds at the source paths, and AlifeAmbience provides the nature/weather ambience those packs leave for the base, the two compose without doubling:
the AlifeSpooks director places the horror, and the AlifeAmbience config plays the living ambience. Run both.

## Content pipeline (reproducible)

`tools/merge.py` is a pipeline. Each stage reads the previous stage's output on disk. `python merge.py rebuild` wipes and regenerates the whole corpus, and each stage also runs alone.
`fold` is the long one (per-file ffmpeg). `add` reruns without wiping, but `graft` appends, so `rebuild` is the path after any config or roster change.

```
plan     hash the roster packs' oggs, dedup by path                     -> manifest.json
deploy   copy the chosen files + the Amplified config subset (spine)     -> gamedata/
config   fix stock defects, strip dead refs, cap spawn distance per cat  -> gamedata/ (config)
graft    wire best-of-breed folders into channels + presets; frogs/heli  -> gamedata/ (config)
fingerprint  acoustic dedup by Chromaprint - collapse same-recording aliases -> gamedata/ (config, sounds)
prune    delete every file no channel references                        -> gamedata/sounds
fold     stereo -> mono (re-encode) + resample off-rate to 44100        -> gamedata/sounds, fold_blobs.json
master   RETIRED no-op (min floor moved into level, crest-inverted)     -> -
level    crest-inverted min floor + loudness band, one crest+LUFS pass  -> gamedata/sounds, level_cache.json
cull     delete silent/dead files, strip refs (never empty a channel)   -> gamedata/sounds
verify   config-closure ledger (6 invariants)                           -> ledger.tsv
audit    wired min/felt-far ratio + crushed share (acceptance gate)     -> stdout
```

The min-distance floor and the loudness band consolidate into `level`, so both key off one crest+LUFS measurement (matching AlifeSpooks' `_normalize_blobs`).
`master` is a retired no-op kept for stage compatibility. An audio-page hash caches the LUFS/crest measurement, so a rerun re-measures only new audio.
`cull` runs after `level` (it needs the measurement) and re-prunes so no ref dangles.

Sources are the registry `tools/sources.py`: one entry per pack (name, path, url, licence, role). A licence gate stops the build on any source not cleared. You pull sources locally by hand,
and the pipeline never downloads, so `url` is a credit/provenance reference only.

## Invariants

- I1 Ambience only. AlifeAmbience owns the continuous nature/weather ambience. Horror one-shots are AlifeSpooks. Emission and psi-storm are their own systems, and the build never touches them.
- I2 Audible and leveled, by measurement. Three levers make a file sound: mono fold (only mono positions), a crest-inverted `min_distance` floor (the OpenAL rolloff anchor),
  and a `base_volume` loudness band (floor lifts quiet, ceiling eases hot) to an ear-calibrated target computed from delivered loudness. The game's ambient volume slider sets the overall level on top.
- I3 Preserve the source, except where the engine forbids it. `level` rewrites only the ogg comment blob (min/max/base_volume), losslessly, leaving the audio pages byte-identical. The one exception is `fold`:
  a stereo file must become mono (a lossy re-encode) because the engine only positions mono, and it captures the author blob first so `level` can restore and then floor min/max/base_volume.
- I4 Deduplicate twice: by byte hash in `plan`, then by acoustic fingerprint (Chromaprint) in `fingerprint`. Both run on our side, never against the target install.
- I5 Config is closed. The six-invariant ledger passes, or the build fails. No silent map, no silent weather, no dangling ref.
- I6 Weather-mod-bound at exactly one link. The preset state set covers the active weather mod's emitted states. Nothing else depends on the weather mod.
- I7 Reproducible. `plan -> deploy -> config -> graft -> fingerprint -> prune -> fold -> master -> level -> cull -> verify -> audit` (`merge.py rebuild`) regenerates the whole soundscape and its proofs from the packs.
- I8 Traceable. Every deployed sound resolves to its origin via `manifest.json`. The readme credits every source, and `licensing.md` clears it.

## Scripts: dependency gate, MCM, diagnostics (no gameplay)

AlifeAmbience provides audio and config. Its Lua is a thin diagnostic and compatibility layer only, a mirror of the family shape so its tooling reads identically to the other mods.
No gameplay logic runs.

- `_aa_deps.script` - the version constant (`get_version`), the xlibs + modded-exes floor asserts, the `platform_status`/`platform_functor` line, and the boot banner to `alifeambience.log`.
  Because it has scripts, the compatibility floor (xlibs + demonized/AOE) applies to AlifeAmbience on load, uniform with the family (`compatibility-standards.md`).
- `aa_mcm.script` - the MCM menu, informational: a General tab with the platform/version footer, and a Development tab (log level, the "log ambient wiring on load" toggle, reset).
  There is NO master volume slider. The build levels loudness into the blob (I2), and the game's own ambient volume slider sets the overall level.
  A per-mod slider would need a runtime ambient hook this config-only mod does not have.
- `aa_debug.script` - one xlog logger plus the `aa_debug.on()/dbg()/info()/warn()` gate, level from MCM.
- `aa_diag.script` - the runtime wiring inspector. On load (and on demand via `aa_diag.dump()` from the console) it logs the active level, weather, and ambient state.
  It reports the per-state dynamic channel counts of the current preset (the density picture that explains why one install fires more often than another), the active background channel and whether it resolves,
  and a live dangling-ref count. Gated on DEBUG or the Development toggle.

## Deploy

A gamedata overlay. The repo holds the buildable source, the tool, the docs, and the audio.
Wired for local sync through `stalker-manager`.
Every source carries a free license or the author's permission, granted for my mods, not per mod (see `licensing.md`). The readme credits each author, and nothing enters the build without a license or consent.
