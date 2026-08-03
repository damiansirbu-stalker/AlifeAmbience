# AlifeAmbience - architecture and method

AlifeAmbience is two systems over the untouched engine soundscape for S.T.A.L.K.E.R.
Anomaly / G.A.M.M.A. The ATMOSPHERE system gathers the dark, dreadful, and mournful
sounds from several soundscape packs, measures each one, and composes two of its own
layers (texture + accent) on top of whatever ambient setup is installed, using DLTX. The
DIEGETIC system owns the volume of the in-world sound the game already emits (base radios,
megaphones, campfire instruments) by wrapping the engine's physical-sound path. Neither
replaces the ambient system: one layers onto it, the other tunes what is already there.

This document is the method and the invariants. The build tool is `tools/merge.py`;
every number below is reproduced by a subcommand of it, not chosen by hand.

## Atmosphere model: two own layers over the untouched engine bed

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
- deploy (`cmd_deploy`): accents grouped by (mood, exact-settings-tuple) into `aa_acc_<mood>_<n>` channels (one per distinct source setting, no median), textures by context pool; emit the audio and the DLTX configs. Deterministic - the shipped `N.ogg` numbering is a pure function of the JSON inputs, which is what makes provenance recoverable.
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

- For each of our 21 level presets and each section, aggregate across all four source packs which of OUR channels each author placed in that exact level+section, and map those channels to their (mood, settings) group. A group plays there iff a source author placed one of its channels there - so each channel lands with its own exact settings, exactly where the packs used it.
- Because the section name is time+weather, this inherits night-heavier-dread (night sections carry `out_night_amb`/`out_dark_amb`/night spoops, day-crows drop out), animals-by-time (crows by day, owls at dusk/night), and weather-gating (the weather mood only where the packs placed storm/rain/fog) straight from the source placement.
- Two lore overrides where the generic packs were lazy, cross-checked against S.T.A.L.K.E.R. canon: the underground labs (`environment_underground`/`_more`/`_x18`) get the underground mood in indoor sections only - the source only ever wires them indoors; the haunted `environment_whisper` is reduced to dread + weather (no wildlife, no people).

The texture bed follows context at runtime (`aa_texture.script`): underground (engine
`underground` event) - splitting the lab pool from the sewer pool by `level.name()`
against the game's own X-Lab level names - then weather (storm/rain, then fog), then
time of day (the dread drone-bed dusk-to-dawn, the lighter wind-bed by day, via
`level.get_time_hours()`).

## Provenance and proof

- `provenance.tsv` (`cmd_provenance`): every shipped `N.ogg` -> original mod, directory, filename, source channel, that channel's LTX `min/max_distance`/`period0-3`/`indoor`/`height`, the gain applied, and the exact list of original `level:time:weather` sections it played in. Nothing loses its origin under the `N.ogg` rename.
- Self-verification: the deterministic deploy is re-derived and every VERBATIM shipped file is md5-compared to its claimed source. Current build: 1730 of 1933 verbatim match, 0 mismatch (the other 203 are loudness-gained, so bytes differ by design) - the rename is proven lossless and the provenance exact.
- `ledger.tsv` (`cmd_ledger`): hash every source ogg against the deployed set and categorise: USED-shipped, USED-gained (shipped after loudness gain, so bytes differ), HELD-texture-surplus (a captured loop beyond the per-bed cap), EMISSION-excluded (by design), OFFSPEC-48k-excluded, off-scope-or-dup, SKIP-nonambient, and UNUSED-DARK. The invariant: **UNUSED-DARK = 0** - no dark, playable file is left uncaptured. Current: UNUSED-DARK 0, USED-shipped 2535, USED-gained 940, HELD 1012, EMISSION 279, OFFSPEC 5.

## Numbers (current build)

- Pooled 5441 -> 2596 dark sounds kept (content-hash dedup + folder-tree capture).
- Classified: 1703 accent, 893 texture (vocals forced accent).
- ACCENT: 1703 sounds in 36 channels grouped by (mood, exact-settings-tuple) - dread 8, underground 12, weather 7, human 4, animal 5 channels. Each channel carries its VERBATIM source settings (min/max distance, four periods, indoor, height), NOT a median; the mood is only a tag for the MCM knobs (aa_sound reads it off `aa_acc_<mood>_<n>`). The old 5-mood median is retired - it flattened varied periods (weather collapsed to a constant 5s = "always windy") and hid degenerate source settings (period-0 channels that would spam).
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
- I13 Runtime control is opt-in. Per-mood knobs and the trace layer own the vanilla ambient play only while a feature is active, and hand the slot back when all return to neutral.
- I14 Neutral is pass-through. With every knob at 1.0 and the trace off, the mod does not own the engine event slot: vanilla runs untouched, zero added cost.
- I15 Diegetic sets volume from the base, never a read-back. The diegetic layer computes `volume = base * mult` from the section condlist each tick; it never reads the value it last wrote and multiplies again, which would compound frame to frame against ph_sound's 50ms throttle.

## Tools and data artifacts

- Signal analysis: `ffmpeg` (`aspectralstats` centroid/flatness, `astats` crest, `ebur128` loudness, `volume`+`libvorbis` gain), `ffprobe` (duration/rate/codec/bitrate). Dedup: md5. Chromaprint `fpcalc` evaluated and rejected. Resolved from `$PORTX_ROOT/packages` by `soundpool.py`.
- Committed data (the audit trail): `merged_channels.json` (pool + per-channel source LTX), `classification.json` (measured features + role per sound), `loudness_outliers.json` (the gained set), `ledger.tsv` (coverage proof), `provenance.tsv` (origin of every shipped sound), `pools.json` (legacy candidate registry for the standalone `soundpool.py`; the authoritative source list is `merge.py` MODS).
- `merge.py` the pipeline (its `MODS` list is the source of truth); `soundpool.py` the probe/resolver (helper functions used by `merge.py`; its `inventory`/`select` CLI over `pools.json` is legacy).

Adopting a pack: refresh it on disk, add it to `merge.py` MODS (the authoritative
source list), re-run the pipeline, read the ledger (UNUSED-DARK must stay 0) and the
provenance self-verify (0 mismatch). Nothing is added by hand.

## Deploy

A DLTX overlay: it can sit anywhere in load order and still compose. Wired via
`stalker-manager` (a `repo:` external for local sync, a `git:` external for the
gamma-redux install). Distributed as a GitHub release / moddb; the repo holds the
buildable source (tool + docs + the audio).

## Runtime control, trace, MCM

Scripts add control, an in-game trace, and the MCM over both systems, mirroring the
alife-family pattern (`at_mcm`/`at_debug`/`xmcm`/`xlog`). All are guarded: without xlibs
they degrade to no-ops and the mod runs content-only on any Anomaly. `_aa_deps.script` is a
SOFT xlibs check (`is_compatible`, family deps format): it warns when xlibs is present but
older than the floor, and never aborts, so a stock install still runs content-only.

- `aa_sound.script` (Atmosphere) owns the dynamic-ambient play, but only while a knob is off-neutral or the trace is on. The vanilla one-shot loop is `sound_ambient.update_ambient`, a `CreateTimeEvent` action dispatched by stored function value (`_g.script:374`) into an EMPTY slot only (`:345`), with no callback and file-local state (`snd_chanels`/`next_idx`/`opt`) no other script can read. The only Lua path in is `RemoveTimeEvent` then `CreateTimeEvent` of a faithful clone (own state, public API only) with per-mood volume/rarity/distance knobs and trace at the vanilla injection points. GAMMA runs the vanilla script unmodified (verified), so the clone matches what ships. Neutral is pass-through (I14).
- `aa_diegetic.script` (Diegetic) owns the in-world audio. It wraps `ph_sound.snd_source.update` (core script; present on vanilla and the Anomaly Radio Extended override), classifies each emitter by its theme (radio / megaphone / other, cached per source), and after calling the original sets the played sound's volume to `base * mult` - where `base` is the section condlist volume, recomputed each tick, NOT the value last written. Reading back the written volume compounds frame to frame: the binder updates per frame (`bind_physic_object.script:45-55`) but ph_sound rewrites volume only on its own 50ms throttle, so `volume = volume * mult` sawtooths; computing from the condlist base is stable (I15). Instruments have no volume seam upstream - `guitar_anim.play_guitar` bakes volume into a local no-feedback play (`guitar_anim.script:45-50`) - so it replaces `play_guitar`/`play_harmonica` with one parameterized helper. Neutral is pass-through: at mult 1.0 the emitter is left to vanilla.
- `aa_debug.script` is the trace facade (mirrors `at_debug`): one logger, one integer gate. At DEBUG it records every accent (channel, mood, file, distance, volume) to `alifeambience.log`, so the soundscape is checked by observation. Below DEBUG the off path marshals nothing and crosses no luabind bridge.
- `aa_mcm.script` is one MCM page tree with two tabs, Atmosphere and Diegetic (the at_mcm `_key_to_tab` + nested `path_builder`; the saved path is `aa/<tab>/<key>` and matches the tree). Atmosphere: per-mood volume, rarity, distance, texture volume, trace log level. Diegetic: master plus per-source volume/enable/frequency for radio, megaphone, guitar, harmonica. Every control is 1.0 = pass-through. Labels in EN + RU (`configs/text/{eng,rus}/ui_st_mcm_aa.xml`, windows-1251 for RU).

## Future (not built)

A demonized-exe callback at the engine static-bed play site, registered through the xlibs
fallback, to extend per-mood control to the C++ background bed. Not required for the current
model: texture volume is native and accents are levelled and controllable through the clone.
Planned content: original sounds recorded for this mod and scripted event sequences.

## Baseline (measured 2026-08-02)

Reference values measured from vanilla Anomaly + GAMMA soundscape mods + the source packs,
not hand-chosen. `src: tested`. Parallel channels per place (`sound_channels_dynamic` length
per level preset x time):

| Source | Places | Avg | Median | p90 | Max |
|--------|--------|-----|--------|-----|-----|
| vanilla Anomaly | 72 | 9.7 | 9 | 12 | 13 |
| Soundscape Overhaul | 240 | 5.6 | 5 | 8 | 11 |
| Dark Signal Weather | 240 | 5.6 | 5 | 8 | 11 |
| RETUNE | 241 | 6.6 | 6 | 11 | 13 |
| Dark Signal Amplified | 349 | 5.7 | 5 | 8 | 11 |

Ceiling 13 (vanilla max, no pack exceeds it); target avg ~10. The old full-override build
peaked at 26 (the overload to avoid). Dark-channel settings (n=223 defs): min_distance 2..120
(median 45), max_distance 3..300 (median 80), periods median 10000/15000/14000/26000 ms.
Loudness (187 sampled sounds): -60.3..-12.8 LUFS, median -32.6, stdev 10.4; within-channel
spread up to 17 LUFS, which is why leveling is per-group median, outliers-only. Measured by
`merge.parse_presets` (counts), `merge.parse_channels` (settings), `ffmpeg ebur128` (loudness).

### Vanilla vs GAMMA horror delta (measured 2026-08-03)

Vanilla places fake horror in nearly every ambient section; GAMMA (Soundscape Overhaul, the
horror-stripper) removes it. Measured over the preset sections (`ambients/presets/environment_*.ltx`):

| Baseline | channels/section (avg / max) | horror/section (avg) | fauna/section |
|----------|------------------------------|----------------------|---------------|
| vanilla | 9.7 / 13 | 4.9 | 0.85 |
| GAMMA (Soundscape Overhaul) | 5.6 / 11 | 2.4 | 0 |

Strip/restore delta - horror channels vanilla places that GAMMA drops: `out_screams`,
`out_mutants`, `out_gunfire`, `wind_dark` (the fake mutant/scream ambience). GAMMA KEEPS the
subtle dread (`out_spooks`, `out_drone`, `out_dark_amb`, + the underground set) and removes
fauna-as-horror (crows/owls/dogs) from ambient entirely. So the overlay DLTX-strips those four
on vanilla to reach GAMMA's floor (a no-op on GAMMA, already gone), keeps GAMMA's subtle dread,
and restores CURATED horror back toward vanilla density (~5 horror/section, target ~10 total)
with real sounds instead of the fake screams/mutants.

## Per-area distribution profile (canon x placement)

Placement is evidence-driven (`write_presets._section_moods`: a mood plays in a level+section
iff a source pack placed a channel of that mood there), refined by S.T.A.L.K.E.R. canon for the
specials. The evidence agrees with canon on 19 of 21 levels; the 2 overrides are underground
labs (indoor sections only) and whisper (dread + weather, no wildlife/people).

| preset | canon area / terrain | human | atmosphere | placement |
|--------|----------------------|-------|------------|-----------|
| cemetary | Truck Cemetery - rusted vehicle graveyard | light | eerie, exposed | dread+weather+animal+light human |
| darkscape | Darkscape - dark wooded rocky valley | light (bandits) | oppressive, dim | dread-heavy+animal+weather |
| field | open fields (Cordon/Agroprom) | moderate | windswept | full |
| forest | forested levels - dense canopy | moderate | enclosed | dread+animal+human, less weather |
| garbage | Garbage - junkyard reclaimed by nature | moderate (bandits) | desolate | full |
| generators | Generators - irradiated forest+industrial | Monolith | irradiated, tense | dread+human heavy+weather, some crows |
| hospital | Pripyat/Limansk hospital interior | none (ghost) | claustrophobic, decay | dread+human+light animal, low weather |
| jupiter | Jupiter (CoP) - factory+fields+underground | heavy | industrial, mixed | full incl human |
| npp | Chernobyl NPP - reactor, Monolith | Monolith | irradiated, dark | dread+human heavy+weather, some crows |
| pripyat | Pripyat - overgrown ghost city | Monolith | haunting ruin | dread+human+animal, low weather |
| pripyat_outskirts | Pripyat approach - ruin + field edge | Monolith/loner | ruin, exposed | as pripyat |
| rostok | Rostok/Bar - Duty hub, industrial urban | HEAVY (safe hub) | populated, industrial | human+dread+animal (dread rarer here - future) |
| rostok_wild | Wild Territory - industrial ruins | mercs (light) | ambush, tense | dread heavy+human+animal+night spoops |
| swamp | Great Swamps - marsh, water, fog | light (Clear Sky) | foggy, wet, eerie | full+weather(fog) heavy+animal |
| underground | generic tunnels/sewers/catacombs | none | dripping, claustrophobic | underground only, indoor |
| underground_more | more tunnel variants | none | claustrophobic | underground only |
| underground_x18 | Lab X18 - dark lab, poltergeists | none | darkest, psi, machinery | underground only |
| urban | Dead City / Limansk ruins | mercs/Monolith | desolate urban | dread+human+animal, low weather |
| whisper | haunted whisper level | none | HAUNTED, whispering | dread+weather only (override) |
| yantar | Yantar - dead lake/swamp, bunker, zombies | Ecologists+zombies | PSI, sickly, foggy | dread(psi)+human(sci drones)+weather+animal |
| zaton | Zaton (CoP) - dried swamp, shipwrecks | loners/bandits | desolate wetland, foggy | full+weather+animal |

Texture bed selection (`aa_texture.script want_bed`, one pool audible at a time): underground
(engine event) splits LAB pool on the X-Lab level names vs SEWER pool elsewhere; then weather
(storm/rain > 0.3 -> stormrain, foggy/tuman -> fog); then time of day (dusk-to-dawn dread bed,
daylight wind bed). The lab/sewer split is per-CLASS, not per-level (per-level would be invented).
