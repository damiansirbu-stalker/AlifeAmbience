# AlifeAmbience - architecture and method

A dark-mood ambient overlay for S.T.A.L.K.E.R. Anomaly / G.A.M.M.A. It gathers the
dark, dreadful, and mournful sounds from several soundscape packs, measures each
one, and composes two of its own layers on top of whatever ambient setup is
installed, using DLTX. It does not replace the ambient system; it layers onto it.

This document is the method and the invariants. The build tool is `tools/merge.py`;
every number below is reproduced by a subcommand of it, not chosen by hand.

## Model: two own layers over the untouched engine bed

The engine's static bed (`sound_channels`, C++ `CGamePersistent::WeathersUpdate`)
is never touched. AlifeAmbience adds two independent layers, split by how a sound
behaves in the mix, decided per file by measurement (below), not by its name:

- TEXTURE - continuous LOOPED beds (drones, whispers, fog, wind, rain, tunnels). One bed at a time by context, low, crossfaded. `xr_sound.play_sound_looped` + `set_volume_sound_looped`, native volume, no engine hook. Driven by `gamedata/scripts/aa_texture.script`, which reads a `sound_theme` of `type=looped` per pool. This is the `update_wind` pattern (`sound_ambient.script:180-237`), generalised to six pools: wind, dread, fog, stormrain, and underground split lab vs sewer (the X-Lab levels sound unlike the tunnels).
- ACCENT - dynamic ONE-SHOT scares (screams, spooks, mutant calls, drips, gunfire). DLTX `sound_channels_dynamic` channels appended per preset section; the vanilla `sound_ambient.script` round-robin plays them positionally (`:86-178`). Loudness-levelled at build time.

Full engine + Lua mechanics with `file:line` are in the stalker-dev library note
`doc/library/anomaly/internals/ambient-sound-system.md`.

## Content pipeline (reproducible)

`tools/merge.py` is a six-stage pipeline; each stage is a subcommand that reads the
previous stage's committed artifact and writes the next. A pack change is a re-run,
not a rewrite.

```
plan       source packs' configs + folder trees -> merged_channels.json
classify   measured signal features per sound   -> classification.json
loudness   per-group median leveling (outliers) -> loudness_outliers.json
deploy     the two layers + DLTX configs        -> gamedata/
ledger     content-hash proof of coverage       -> ledger.tsv
provenance every shipped file -> its origin      -> provenance.tsv
```

- plan (`cmd_plan`): parse each pack's `sound_channels.ltx`; pool each dark channel's sounds; ALSO walk the FOLDER TREES (`DARK_FILL`), because the packs ship far more dark content than any channel references. Resolve to files, dedup by content hash, gate on codec+rate. Output `merged_channels.json`.
- classify (`cmd_classify`): measure every pooled sound and assign its role (below).
- loudness (`cmd_loudness`): measure integrated loudness and flag per-group outliers (below).
- deploy (`cmd_deploy`): group by mood/context, emit the audio and the four DLTX configs. Deterministic - the shipped `N.ogg` numbering is a pure function of the JSON inputs, which is what makes provenance recoverable.
- ledger (`cmd_ledger`) and provenance (`cmd_provenance`): the proofs (below).

## Measurement and signal analysis (the techniques)

Role is not guessed from a channel name. Each sound is measured with signal-analysis
CLIs and classified on the measured values.

Feature extraction, per file, one `ffprobe` + one `ffmpeg` pass:

| Feature | Tool / filter | Meaning |
|---------|---------------|---------|
| duration | `ffprobe` stream duration | bed vs one-shot length |
| spectral centroid | `ffmpeg aspectralstats=measure=centroid` | brightness (Hz) |
| spectral flatness | `ffmpeg aspectralstats=measure=flatness` | tonal (near 0) vs noise-like (near 1) |
| crest factor | `ffmpeg astats` | peak-to-RMS: transient (high) vs steady (low) |
| integrated loudness | `ffmpeg ebur128` (I, LUFS) | EBU R128 program loudness |
| sample rate / codec / bitrate | `ffprobe` | fitness gate + dedup tiebreak |

Measured role decision (`_classify_one`):
- duration >= 30 s -> TEXTURE (a bed); duration < 4 s -> ACCENT (an event).
- otherwise TEXTURE iff crest < 12 AND flatness < 0.40 (steady and non-transient), else ACCENT.
- VOCAL channels (screams, spooks, mutant calls) are FORCED to accent regardless of length: a wail is an event, never a loop.
- brightness label from centroid (dark < 2000 Hz < mid < 4000 Hz < bright); tonality label from flatness (tonal < 0.15 < mixed < 0.40 < noisy). Recorded for inspection.

Proof the split is real, not nominal: a drone measures 181 Hz centroid / 0.04
flatness (dark, tonal, steady -> texture) against a scream at 1276 Hz and tonal but
short and transient (-> accent), and wind at 7658 Hz (bright, noisy).

Deduplication: exact content hash (md5) over the file bytes. Byte-identical reships
across packs collapse to one; distinct sounds never merge. Acoustic fingerprinting
(Chromaprint `fpcalc`) was evaluated and REJECTED: on this corpus it merged 25
distinct screams to 4 - acoustic similarity is not identity.

Loudness leveling: per group (channel/bed) take the MEDIAN integrated LUFS as the
group level, and gain back only the OUTLIERS - files where |LUFS - median| >
max(6, 1.5 x IQR). Everything inside the band is shipped verbatim (no re-encode, no
quality loss); outliers are re-encoded with `ffmpeg volume=<median-LUFS>dB`,
preserving dynamics. This is deliberately NOT a global normalize: slamming a whisper
and a scream to one level would flatten the mix. On the measured data 148 of 2596
(6%) are outliers; the rest ship untouched.

Fitness gate: 44100 Hz vorbis only (the X-Ray standard); off-rate and junk-bitrate
files are dropped and accounted (never silently).

## Distribution: evidence-driven, per (level, time, weather)

The vanilla ambient section name carries both time (`day`/`evening`/`morning`/
`night`) and weather (`rain*`, `pre_storm`, `storm_*`, `tuman*`) plus the indoor set.
Placement is TRACED from how the pack authors used the sounds, not invented
(`write_presets._section_moods`):

- For each of our 21 level presets and each section, aggregate across all four source packs which of OUR channels each author placed in that exact level+section, and map those channels to our five moods. A mood plays there iff a source author placed a channel of that mood there.
- Because the section name is time+weather, this inherits night-heavier-dread (night sections carry `out_night_amb`/`out_dark_amb`/night spoops, day-crows drop out), animals-by-time (crows by day, owls at dusk/night), and weather-gating (the weather mood only where the packs placed storm/rain/fog) straight from the source placement.
- Two lore overrides where the generic packs were lazy, cross-checked against S.T.A.L.K.E.R. canon: the underground labs (`environment_underground`/`_more`/`_x18`) get the underground mood in indoor sections only - the source only ever wires them indoors; the haunted `environment_whisper` is reduced to dread + weather (no wildlife, no people).

The texture bed follows context at runtime (`aa_texture.script`): underground (engine
`underground` event) - splitting the lab pool from the sewer pool by `level.name()`
against the game's own X-Lab level names - then weather (storm/rain, then fog), then
time of day (the dread drone-bed dusk-to-dawn, the lighter wind-bed by day, via
`level.get_time_hours()`).

## Provenance and proof

- `provenance.tsv` (`cmd_provenance`): every shipped `N.ogg` -> original mod, directory, filename, source channel, that channel's LTX `min/max_distance`/`period0-3`/`indoor`/`height`, the gain applied, and the exact list of original `level:time:weather` sections it played in. Nothing loses its origin under the `N.ogg` rename.
- Self-verification: the deterministic deploy is re-derived and every VERBATIM shipped file is md5-compared to its claimed source. Current build: 1584/1584 match, 0 mismatch - the rename is proven lossless and the provenance exact.
- `ledger.tsv` (`cmd_ledger`): hash every source ogg against the deployed set and categorise: USED-shipped, USED-gained (shipped after loudness gain, so bytes differ), HELD-texture-surplus (a captured loop beyond the per-bed cap), EMISSION-excluded (by design), OFFSPEC-48k-excluded, off-scope-or-dup, SKIP-nonambient, and UNUSED-DARK. The invariant: **UNUSED-DARK = 0** - no dark, playable file is left uncaptured. Current: UNUSED-DARK 0, USED-shipped 2535, USED-gained 940, HELD 1012, EMISSION 279, OFFSPEC 5.

## Numbers (current build)

- Pooled 5441 -> 2596 dark sounds kept (content-hash dedup + folder-tree capture).
- Classified: 1703 accent, 893 texture (vocals forced accent).
- ACCENT: 5 mood channels, 1703 sounds - dread 933, underground 307, weather 211, human 169, animal 83. All `min_distance 45 / max_distance 100 / period 20000..60000`.
- TEXTURE: 6 looped pools - wind, dread, fog, stormrain, underground_lab, underground_sewer - up to 40 loops each by duration (230 total; fog ships all 30). 663 texture variations HELD as surplus beyond the caps (tracked in the ledger, not shipped).
- Shipped total 1933; loudness gain applied to 148 outliers.

## Invariants

- I1 Compose, never override. Ship DLTX patches over the ambient config; the engine bed and its asserted channels stay intact, so an overlay cannot cause a missing-channel CTD.
- I2 Two layers, split by measurement. Texture = looped bed; accent = dynamic one-shot; the boundary is the measured duration/crest/flatness, not the name.
- I3 Dedup by exact content hash (md5). Acoustic fingerprinting is not used.
- I4 Fitness is codec + sample rate: 44100 Hz vorbis. Off-spec files are dropped and accounted.
- I5 Loudness by per-group median leveling, outliers only. Preserve dynamics; texture beds sit below accents; distance varies at play.
- I6 Capture from folder trees, not just channel-wired files. The proof that this matters is the ledger: it is what drives UNUSED-DARK to 0.
- I7 Distribution is traced from the source configs, refined by canon for the specials. No flat map; no random placement.
- I8 Variety is free. A channel/bed may hold as many sounds as pass I3/I4; the surplus beyond a bed cap is held and accounted, never dropped.
- I9 Dark scope only. Keep dread/horror/underground/eerie/oppressive-weather; leave generic daytime life to the base ambience.
- I10 Leave emission alone. Blowout and psi-storm are their own system.
- I11 Reproducible. plan -> classify -> loudness -> deploy -> ledger -> provenance regenerates the whole overlay from the packs.
- I12 Traceable. Every shipped sound resolves to its origin via `provenance.tsv`; every source file resolves to a ledger category. Credit every source pack (author + link) in the readme.

## Tools and data artifacts

- Signal analysis: `ffmpeg` (`aspectralstats` centroid/flatness, `astats` crest, `ebur128` loudness, `volume`+`libvorbis` gain), `ffprobe` (duration/rate/codec/bitrate). Dedup: md5. Chromaprint `fpcalc` evaluated and rejected. Resolved from `$PORTX_ROOT/packages` by `soundpool.py`.
- Committed data (the audit trail): `merged_channels.json` (pool + per-channel source LTX), `classification.json` (measured features + role per sound), `loudness_outliers.json` (the gained set), `ledger.tsv` (coverage proof), `provenance.tsv` (origin of every shipped sound), `pools.json` (source registry).
- `merge.py` the pipeline; `soundpool.py` the probe/resolver.

Adopting a pack: refresh it on disk, add it to `MODS`/`pools.json`, re-run the
pipeline, read the ledger (UNUSED-DARK must stay 0) and the provenance self-verify
(0 mismatch). Nothing is added by hand.

## Deploy

A DLTX overlay: it can sit anywhere in load order and still compose. Wired via
`stalker-manager` (a `repo:` external for local sync, a `git:` external for the
gamma-redux install). Distributed as a GitHub release / moddb; the repo holds the
buildable source (tool + docs + the audio).

## Future (not built)

An MCM page with per-mood knobs (volume, rarity, distance, max-at-once) and an
announce diagnostic, mirroring the alife-family pattern (`at_mcm`/`xmcm`/`xlog`/
`xprofiler`). A demonized-exe callback at the engine static-bed play site, registered
through the xlibs fallback, to extend control to the C++ bed. Neither is required for
the current model to be correct: texture volume is native, accents are levelled.
